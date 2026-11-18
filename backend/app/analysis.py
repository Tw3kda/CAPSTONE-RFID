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


def recommendation_context(db):
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=90)
    unused = reusable_assets(db, now)
    maintenance = db.scalars(
        select(Activo).where(Activo.estado == "en_revision").order_by(Activo.id)
    ).all()
    # Keep both reuse and maintenance represented while bounding external disclosure/cost.
    candidates = sorted(unused[:4] + maintenance[:4], key=lambda asset: asset.id)
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
