from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import exists, func, select

from app.models import Activo, Evento, Prestamo
from app.recommendations import Recomendacion, generate_recommendation
from app.schemas import ActivoOut
from app.security import Admin, Db
from app.services import asset_view

analysis = APIRouter(prefix="/api/analisis", tags=["Análisis"])


class UsoSemanal(BaseModel):
    semana: str
    movimientos: int


class ResumenAnalisis(BaseModel):
    disponibles: int
    prestados: int
    en_revision: int
    uso_semanal: list[UsoSemanal]
    baja_utilizacion: list[int]


def reusable_assets(db, now):
    recent_withdrawal = exists(
        select(Prestamo.id).where(
            Prestamo.activo_id == Activo.id,
            Prestamo.retiro_at >= now - timedelta(days=90),
            Prestamo.retiro_at <= now,
        )
    )
    return db.scalars(
        select(Activo)
        .where(
            Activo.estado == "disponible",
            Activo.presente.is_not(False),
            ~recent_withdrawal,
        )
        .order_by(Activo.id)
    ).all()


def analysis_summary(db, now):
    cutoff = now - timedelta(days=90)
    counts = dict(
        db.execute(
            select(Activo.estado, func.count())
            .where((Activo.estado != "disponible") | Activo.presente.is_not(False))
            .group_by(Activo.estado)
        ).all()
    )
    week_expression = func.date_trunc("week", Prestamo.retiro_at)
    weekly = dict(
        db.execute(
            select(
                week_expression,
                func.count(),
            )
            .where(Prestamo.retiro_at >= cutoff, Prestamo.retiro_at <= now)
            .group_by(week_expression)
        ).all()
    )
    week = (cutoff - timedelta(days=cutoff.weekday())).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    series = []
    while week <= now:
        series.append({"semana": week.date().isoformat(), "movimientos": weekly.get(week, 0)})
        week += timedelta(days=7)
    return {
        "disponibles": counts.get("disponible", 0),
        "prestados": counts.get("prestado", 0),
        "en_revision": counts.get("en_revision", 0),
        "uso_semanal": series,
        "baja_utilizacion": [a.id for a in reusable_assets(db, now)],
    }


@analysis.get("/resumen", response_model=ResumenAnalisis)
def summary(db: Db, user: Admin):
    return analysis_summary(db, datetime.now(UTC))


@analysis.get("/reutilizables", response_model=list[ActivoOut])
def reusable(db: Db, user: Admin):
    return [asset_view(a) for a in reusable_assets(db, datetime.now(UTC))]


def resource_usage(db, now):
    """Aggregate confirmed withdrawals; no person, individual loan or deadline leaves SQL."""
    duration = func.extract("epoch", Prestamo.devolucion_at - Prestamo.retiro_at) / 3600
    completed = (
        (Prestamo.estado == "devuelto")
        & (Prestamo.devolucion_at >= Prestamo.retiro_at)
        & (Prestamo.devolucion_at <= now)
    )
    rows = db.execute(
        select(
            Prestamo.activo_id,
            func.count().label("retiros_90d"),
            func.count()
            .filter(Prestamo.retiro_at >= now - timedelta(days=30))
            .label("retiros_30d"),
            func.count()
            .filter(
                (Prestamo.retiro_at >= now - timedelta(days=60))
                & (Prestamo.retiro_at < now - timedelta(days=30))
            )
            .label("retiros_30d_anteriores"),
            func.count().filter(completed).label("devoluciones_90d"),
            func.percentile_cont(0.5).within_group(duration).filter(completed).label("mediana"),
            func.max(duration).filter(completed).label("maxima"),
        )
        .where(Prestamo.retiro_at >= now - timedelta(days=90), Prestamo.retiro_at <= now)
        .group_by(Prestamo.activo_id)
    )
    return {
        row.activo_id: {
            "retiros_90d": row.retiros_90d,
            "retiros_30d": row.retiros_30d,
            "retiros_30d_anteriores": row.retiros_30d_anteriores,
            "devoluciones_90d": row.devoluciones_90d,
            "duracion_mediana_horas": round(float(row.mediana), 2)
            if row.mediana is not None
            else None,
            "duracion_maxima_horas": round(float(row.maxima), 2)
            if row.maxima is not None
            else None,
        }
        for row in rows
    }


def recommendation_context(db):
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=90)
    unused = reusable_assets(db, now)
    maintenance = db.scalars(
        select(Activo).where(Activo.estado == "en_revision").order_by(Activo.id)
    ).all()
    usage = resource_usage(db, now)
    assets = db.scalars(select(Activo).order_by(Activo.id)).all()
    ranked = sorted(
        assets, key=lambda asset: (-usage.get(asset.id, {}).get("retiros_90d", 0), asset.id)
    )
    # Represent maintenance, low use and observed demand; the bound is disclosure, not a score.
    chosen = {asset.id: asset for asset in maintenance[:2] + unused[:2] + ranked[:4]}
    for asset in ranked:
        if len(chosen) >= 8:
            break
        chosen.setdefault(asset.id, asset)
    candidates = sorted(chosen.values(), key=lambda asset: asset.id)
    related = [asset.id for asset in candidates]
    # An observation older than the window is evidence of historical tracking, not a prediction.
    observed = set(
        db.scalars(
            select(Evento.activo_id).where(
                Evento.ocurrido_at <= cutoff, Evento.activo_id.in_(related)
            )
        )
    )
    observed.update(
        db.scalars(
            select(Prestamo.activo_id).where(
                Prestamo.retiro_at <= cutoff,
                Prestamo.activo_id.in_(related),
            )
        )
    )
    insufficient = not related or any(asset_id not in observed for asset_id in related)
    metrics = analysis_summary(db, now)
    return {
        "periodo_dias": 90,
        "inventario": {
            field: metrics[field] for field in ("disponibles", "prestados", "en_revision")
        },
        "uso_semanal": metrics["uso_semanal"],
        "total_baja_utilizacion": len(unused),
        "total_candidatos_mantenimiento": len(maintenance),
        "datos_insuficientes": insufficient,
        "candidatos": [
            {
                "id": asset.id,
                "nombre": asset.nombre,
                "categoria": asset.categoria.nombre,
                "estado": asset.estado,
                "disponible": asset.estado == "disponible" and asset.presente is not False,
                "sin_retiros_90d": asset in unused,
                "uso": usage.get(
                    asset.id,
                    {
                        "retiros_90d": 0,
                        "retiros_30d": 0,
                        "retiros_30d_anteriores": 0,
                        "devoluciones_90d": 0,
                        "duracion_mediana_horas": None,
                        "duracion_maxima_horas": None,
                    },
                ),
                "condicion": asset.condicion,
                "ultima_revision_at": asset.ultima_revision_at.isoformat()
                if asset.ultima_revision_at
                else None,
            }
            for asset in candidates
        ],
    }


@analysis.post("/recomendacion", response_model=Recomendacion)
def recommendation(db: Db, user: Admin):
    context = recommendation_context(db)
    # Release the read transaction/connection before waiting on the external provider.
    db.rollback()
    return generate_recommendation(context)
