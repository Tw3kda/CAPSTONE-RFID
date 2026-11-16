from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import exists, func, select

from app.models import Activo, Evento, Prestamo
from app.schemas import ActivoOut
from app.security import Db, User
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


class Recomendacion(BaseModel):
    texto: str
    activos_relacionados: list[int]
    datos_insuficientes: bool


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
            ~recent_withdrawal,
        )
        .order_by(Activo.id)
    ).all()


@analysis.get("/resumen", response_model=ResumenAnalisis)
def summary(db: Db, user: User):
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=90)
    counts = dict(db.execute(select(Activo.estado, func.count()).group_by(Activo.estado)).all())
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


@analysis.get("/reutilizables", response_model=list[ActivoOut])
def reusable(db: Db, user: User):
    return [asset_view(a) for a in reusable_assets(db, datetime.now(UTC))]


@analysis.post("/recomendacion", response_model=Recomendacion)
def recommendation(db: Db, user: User):
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=90)
    unused = reusable_assets(db, now)
    maintenance = db.scalars(
        select(Activo).where(Activo.estado == "en_revision").order_by(Activo.id)
    ).all()
    related = sorted({a.id for a in unused + maintenance})
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
    parts = []
    if unused:
        parts.append(
            f"Hay {len(unused)} activos disponibles sin retiros registrados en los últimos "
            "90 días. Revise sus fichas antes de adquirir otros."
        )
    if maintenance:
        parts.append(f"Hay {len(maintenance)} activos en revisión; compruebe su mantenimiento.")
    if insufficient:
        parts.append(
            "El historial disponible no cubre 90 días para todos los recursos; "
            "la ausencia de retiros no demuestra desuso. No se realizan predicciones."
        )
    if not parts:
        parts.append("No se identifican recursos disponibles sin uso ni activos en revisión.")
    return {
        "texto": " ".join(parts),
        "activos_relacionados": related,
        "datos_insuficientes": insufficient,
    }
