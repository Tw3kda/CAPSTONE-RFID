from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import select

from app.models import OPEN_LOAN_STATES, Activo, Prestamo, Usuario
from app.realtime import notify_loan
from app.schemas import Input, Ubicacion
from app.security import Db, User
from app.services import get_or_404, loan_view, save

LoanState = Literal[
    "pendiente_retiro",
    "activo",
    "validando_devolucion",
    "esperando_posicion",
    "devuelto",
    "cancelado",
]


class PrestamoNuevo(Input):
    activo_id: int = Field(gt=0)
    responsable_id: int = Field(gt=0)
    devolucion_esperada_at: AwareDatetime


class PrestamoOut(BaseModel):
    id: int
    activo_id: int
    responsable_id: int
    entregado_por_id: int
    activo_nombre: str
    responsable_nombre: str
    entregado_por_nombre: str
    ubicacion_asignada: Ubicacion
    retiro_at: datetime | None
    devolucion_esperada_at: datetime
    devolucion_at: datetime | None
    estado: LoanState


loans = APIRouter(prefix="/api/prestamos", tags=["Préstamos"])


def authorize_loan(loan: Prestamo, user: Usuario):
    if user.rol.nombre == "usuario" and loan.responsable_id != user.id:
        raise HTTPException(403, "Loan belongs to another user")


def locked_asset(db, asset_id: int):
    row = db.scalar(select(Activo).where(Activo.id == asset_id).with_for_update(of=Activo))
    if row is None:
        raise HTTPException(404, "Record not found")
    return row


def locked_loan(db, loan_id: int, user: Usuario):
    row = get_or_404(db, Prestamo, loan_id)
    authorize_loan(row, user)
    locked_asset(db, row.activo_id)
    db.refresh(row)
    return row


@loans.get("", response_model=list[PrestamoOut])
def list_loans(
    db: Db, user: User, alcance: Literal["mios", "todos"] = "mios", estado: LoanState | None = None
):
    query = select(Prestamo)
    if alcance == "todos":
        if user.rol.nombre == "usuario":
            raise HTTPException(403, "Staff role required")
    else:
        query = query.where(Prestamo.responsable_id == user.id)
    if estado is not None:
        query = query.where(Prestamo.estado == estado)
    return [loan_view(loan) for loan in db.scalars(query.order_by(Prestamo.id.desc()))]


@loans.post("", status_code=201, response_model=PrestamoOut)
def create_loan(data: PrestamoNuevo, db: Db, user: User):
    if data.responsable_id != user.id and user.rol.nombre == "usuario":
        raise HTTPException(403, "Staff role required for delegation")
    if data.devolucion_esperada_at <= datetime.now(UTC):
        raise HTTPException(422, "Return date must be in the future")
    responsible = get_or_404(db, Usuario, data.responsable_id)
    if not responsible.activo:
        raise HTTPException(409, "Responsible account is inactive")
    asset = locked_asset(db, data.activo_id)
    existing = db.scalar(
        select(Prestamo.id).where(
            Prestamo.activo_id == asset.id,
            Prestamo.estado.in_(OPEN_LOAN_STATES),
        )
    )
    if asset.estado != "disponible" or existing is not None:
        raise HTTPException(409, "Asset is unavailable")
    row = Prestamo(
        **data.model_dump(),
        entregado_por_id=user.id,
        estado="pendiente_retiro",
        operacion_iniciada_at=datetime.now(UTC),
    )
    db.add(row)
    save(db)
    db.refresh(row)
    notify_loan(row)
    return loan_view(row)


@loans.get("/{id}", response_model=PrestamoOut)
def loan(id: int, db: Db, user: User):
    row = get_or_404(db, Prestamo, id)
    authorize_loan(row, user)
    return loan_view(row)


@loans.post("/{id}/devolucion", status_code=202, response_model=PrestamoOut)
def start_return(id: int, db: Db, user: User):
    row = locked_loan(db, id, user)
    if row.estado != "activo":
        raise HTTPException(409, "Loan is not active")
    row.estado = "validando_devolucion"
    row.operacion_iniciada_at = datetime.now(UTC)
    save(db)
    notify_loan(row)
    return loan_view(row)


@loans.post("/{id}/cancelar-operacion", response_model=PrestamoOut)
def cancel_operation(id: int, db: Db, user: User):
    row = locked_loan(db, id, user)
    if row.estado == "pendiente_retiro":
        row.estado = "cancelado"
    elif row.estado in ("validando_devolucion", "esperando_posicion"):
        row.estado = "activo"
    else:
        raise HTTPException(409, "No pending operation")
    row.operacion_iniciada_at = datetime.now(UTC)
    save(db)
    notify_loan(row)
    return loan_view(row)
