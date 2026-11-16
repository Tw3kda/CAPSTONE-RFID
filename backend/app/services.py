from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Activo, Auditoria, Posicion, Prestamo, Usuario


def get_or_404(db: Session, model, identity):
    row = db.get(model, identity)
    if row is None:
        raise HTTPException(404, "Record not found")
    return row


def save(db: Session):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Data conflicts with an existing record") from None


def audit(db: Session, user: Usuario, action: str, row):
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Data conflicts with an existing record") from None
    db.add(
        Auditoria(
            usuario_id=user.id,
            accion=action,
            entidad=row.__tablename__,
            entidad_id=str(row.id),
            creado_at=datetime.now(UTC),
        )
    )


def user_view(user: Usuario) -> dict:
    return {"id": user.id, "nombre": user.nombre, "rol": user.rol.nombre, "activo": user.activo}


def location_view(position: Posicion) -> dict:
    return {
        "posicion_id": position.id,
        "espacio": position.gabinete.espacio.nombre,
        "gabinete": position.gabinete.nombre,
        "estante": position.estante,
        "codigo": position.codigo,
    }


def asset_view(asset: Activo) -> dict:
    return {
        "id": asset.id,
        "nombre": asset.nombre,
        "codigo": f"ACT-{asset.id:03}",
        "categoria": asset.categoria.nombre,
        "estado": asset.estado,
        "condicion": asset.condicion,
        "ultima_revision_at": asset.ultima_revision_at,
        "ubicacion": location_view(asset.posicion),
    }


def loan_view(loan: Prestamo) -> dict:
    return {
        key: getattr(loan, key)
        for key in (
            "id",
            "activo_id",
            "responsable_id",
            "entregado_por_id",
            "retiro_at",
            "devolucion_esperada_at",
            "devolucion_at",
            "estado",
        )
    } | {
        "activo_nombre": loan.activo.nombre,
        "responsable_nombre": loan.responsable.nombre,
        "entregado_por_nombre": loan.entregado_por.nombre,
        "ubicacion_asignada": location_view(loan.activo.posicion),
    }
