from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import String, cast, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Activo, Auditoria, Categoria, Espacio, Gabinete, Posicion, Prestamo, Usuario


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
        "categoria_id": asset.categoria_id,
        "estado": asset.estado,
        "condicion": asset.condicion,
        "ultima_revision_at": asset.ultima_revision_at,
        "ubicacion": location_view(asset.posicion),
    }


def search_assets(db: Session, q=None, category_id=None, state=None):
    # A catalog response needs scalar fields, not a fully materialized ORM relationship graph.
    query = (
        select(
            Activo.id,
            Activo.nombre,
            Activo.estado,
            Activo.condicion,
            Activo.ultima_revision_at,
            Activo.categoria_id,
            Categoria.nombre.label("categoria"),
            Posicion.id.label("posicion_id"),
            Espacio.nombre.label("espacio"),
            Gabinete.nombre.label("gabinete"),
            Posicion.estante,
            Posicion.codigo,
        )
        .join(Categoria, Activo.categoria_id == Categoria.id)
        .join(
            Posicion,
            Activo.posicion_asignada_id == Posicion.id,
        )
        .join(Gabinete, Posicion.gabinete_id == Gabinete.id)
        .join(
            Espacio,
            Gabinete.espacio_id == Espacio.id,
        )
    )
    if q:
        if q.upper().startswith("ACT-") and q[4:].isdigit():
            query = query.where(Activo.id == int(q[4:]))
        else:
            query = query.where(
                or_(
                    Activo.nombre.ilike(f"%{q}%"),
                    ("ACT-" + cast(Activo.id, String)).ilike(f"%{q}%"),
                )
            )
    if category_id is not None:
        query = query.where(Activo.categoria_id == category_id)
    if state is not None:
        query = query.where(Activo.estado == state)
    return [
        {
            "id": row.id,
            "nombre": row.nombre,
            "estado": row.estado,
            "condicion": row.condicion,
            "ultima_revision_at": row.ultima_revision_at,
            "codigo": f"ACT-{row.id:03}",
            "categoria": row.categoria,
            "categoria_id": row.categoria_id,
            "ubicacion": {
                key: getattr(row, key)
                for key in (
                    "posicion_id",
                    "espacio",
                    "gabinete",
                    "estante",
                    "codigo",
                )
            },
        }
        for row in db.execute(query.order_by(Activo.id))
    ]


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
