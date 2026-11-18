"""Ordinary retention, run explicitly by the administrator's scheduled CLI task."""

from calendar import monthrange
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import engine
from app.models import Auditoria, Evento, Prestamo


def months_before(value: datetime, months: int) -> datetime:
    offset = value.year * 12 + value.month - 1 - months
    year, month = divmod(offset, 12)
    month += 1
    return value.replace(year=year, month=month, day=min(value.day, monthrange(year, month)[1]))


def purge_expired(*, now: datetime | None = None, dry_run: bool = True) -> dict[str, int]:
    if get_settings().retention_hold and not dry_run:
        raise RuntimeError("Retention is suspended by institutional or legal hold")
    now = now or datetime.now(UTC)
    loan_cutoff, audit_cutoff = months_before(now, 24), months_before(now, 12)
    expired_loans = select(Prestamo.id).where(
        or_(
            and_(Prestamo.estado == "devuelto", Prestamo.devolucion_at < loan_cutoff),
            and_(Prestamo.estado == "cancelado", Prestamo.operacion_iniciada_at < loan_cutoff),
        )
    )
    expired_events = and_(
        Evento.recibido_at < now - timedelta(days=90),
        or_(
            Evento.prestamo_id.is_(None),
            Evento.prestamo_id.in_(expired_loans),
        ),
    )
    expired_audit = Auditoria.creado_at < audit_cutoff
    with Session(engine) as db, db.begin():
        counts = {
            "prestamos": db.scalar(select(func.count()).select_from(expired_loans.subquery())),
            "eventos": db.scalar(select(func.count()).select_from(Evento).where(expired_events)),
            "auditoria": db.scalar(
                select(func.count()).select_from(Auditoria).where(expired_audit)
            ),
        }
        if not dry_run:
            db.execute(delete(Evento).where(expired_events))
            # Recent events survive even if the linked loan's ordinary retention has elapsed.
            db.execute(
                update(Evento).where(Evento.prestamo_id.in_(expired_loans)).values(prestamo_id=None)
            )
            db.execute(delete(Prestamo).where(Prestamo.id.in_(expired_loans)))
            db.execute(delete(Auditoria).where(expired_audit))
        return counts
