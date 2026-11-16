import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app.loans import locked_asset
from app.models import (
    OPEN_LOAN_STATES,
    Activo,
    Dispositivo,
    Espacio,
    Evento,
    Gabinete,
    Lector,
    Prestamo,
)
from app.realtime import notify_loan
from app.schemas import UID, Input, Nonempty
from app.security import Admin, Db, User
from app.services import audit, get_or_404, location_view, save


class EspacioNuevo(Input):
    nombre: Nonempty = Field(max_length=120)


class GabineteNuevo(EspacioNuevo):
    espacio_id: int = Field(gt=0)


class DispositivoNuevo(Input):
    id: Nonempty = Field(max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class ProvisionedDevice(BaseModel):
    id: str
    api_key: str


class EntityOut(BaseModel):
    id: int
    nombre: str


class GabineteOut(EntityOut):
    espacio_id: int


class Mapeo(BaseModel):
    uid: str
    activo_id: int
    codigo: str
    canal: int


class Senales(BaseModel):
    canales: list[int]


class Heartbeat(Input):
    arranque: int = Field(ge=0, le=9223372036854775807)
    firmware: Nonempty = Field(max_length=32)
    rssi: int | None = Field(default=None, ge=-2147483648, le=2147483647)


class EventoDispositivo(Input):
    secuencia: int = Field(ge=1, le=9223372036854775807)
    tipo: Literal["INICIO", "PRESENTE", "DEVUELTO", "RETIRADO"]
    canal: int | None = Field(default=None, ge=1)
    uid: UID | None = None
    antiguedad_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def identity_matches_type(self):
        if self.tipo == "INICIO":
            if self.canal is not None or self.uid is not None:
                raise ValueError("INICIO must not include a reader or UID")
        elif self.canal is None or self.uid is None:
            raise ValueError("RFID observations require a reader and UID")
        return self


class Lote(Input):
    arranque: int = Field(ge=0, le=9223372036854775807)
    eventos: list[EventoDispositivo] = Field(min_length=1, max_length=8)


class BatchResult(BaseModel):
    aceptados: int
    duplicados: int


provisioning = APIRouter(prefix="/api", tags=["Administración"])
devices = APIRouter(prefix="/api/dispositivos", tags=["Dispositivos"])
signals = APIRouter(prefix="/api/activos", tags=["Inventario"])


@provisioning.post("/espacios", status_code=201, response_model=EntityOut)
def create_space(data: EspacioNuevo, db: Db, user: Admin):
    row = Espacio(**data.model_dump())
    db.add(row)
    audit(db, user, "crear_espacio", row)
    save(db)
    return row


@provisioning.post("/gabinetes", status_code=201, response_model=GabineteOut)
def create_cabinet(data: GabineteNuevo, db: Db, user: Admin):
    get_or_404(db, Espacio, data.espacio_id)
    row = Gabinete(**data.model_dump())
    db.add(row)
    audit(db, user, "crear_gabinete", row)
    save(db)
    return row


@provisioning.post("/dispositivos", status_code=201, response_model=ProvisionedDevice)
def create_device(data: DispositivoNuevo, db: Db, user: Admin):
    key = secrets.token_urlsafe(32)
    row = Dispositivo(id=data.id, api_key_hash=hashlib.sha256(key.encode()).hexdigest())
    db.add(row)
    audit(db, user, "crear_dispositivo", row)
    save(db)
    return {"id": row.id, "api_key": key}


def authenticated_device(
    dispositivo_id: str, db: Db, key: Annotated[str | None, Header(alias="X-Device-Key")] = None
):
    row = db.get(Dispositivo, dispositivo_id)
    digest = hashlib.sha256((key or "").encode()).hexdigest()
    if row is None or key is None or not hmac.compare_digest(row.api_key_hash, digest):
        raise HTTPException(401, "Invalid device credential")
    return row


Device = Annotated[Dispositivo, Depends(authenticated_device)]


@devices.get("/{dispositivo_id}/configuracion", response_model=list[Mapeo])
def configuration(db: Db, device: Device):
    rows = db.execute(
        select(Activo, Lector.canal)
        .join(
            Lector,
            Activo.posicion_asignada_id == Lector.posicion_id,
        )
        .where(Lector.dispositivo_id == device.id)
        .order_by(Activo.id, Lector.canal)
    )
    return [
        {"uid": a.rfid_uid, "activo_id": a.id, "codigo": f"ACT-{a.id:03}", "canal": channel}
        for a, channel in rows
    ]


@devices.get("/{dispositivo_id}/senales", response_model=Senales)
def poll_signals(db: Db, device: Device):
    channels = db.scalars(
        select(Lector.canal)
        .where(
            Lector.dispositivo_id == device.id,
            Lector.senal_hasta > datetime.now(UTC),
        )
        .order_by(Lector.canal)
    ).all()
    return {"canales": channels}


@signals.post("/{id}/senal", status_code=202)
def signal_asset(id: int, db: Db, user: User):
    asset = get_or_404(db, Activo, id)
    readers = db.scalars(
        select(Lector).where(Lector.posicion_id == asset.posicion_asignada_id)
    ).all()
    if not readers:
        raise HTTPException(409, "Assigned position has no reader")
    for reader in readers:
        reader.senal_hasta = datetime.now(UTC) + timedelta(seconds=30)
    save(db)
    return {"detail": "Signal scheduled"}


@devices.post("/{dispositivo_id}/heartbeat", status_code=204)
def heartbeat(data: Heartbeat, db: Db, device: Device):
    device.firmware = data.firmware
    device.ultimo_rssi = data.rssi
    device.ultimo_heartbeat = datetime.now(UTC)
    save(db)
    return Response(status_code=204)


def process_observation(db, device, boot, observation, reader, received_at):
    uid = observation.uid.upper() if observation.uid else None
    asset_id = db.scalar(select(Activo.id).where(Activo.rfid_uid == uid)) if uid else None
    asset = locked_asset(db, asset_id) if asset_id is not None else None
    loan = (
        db.scalar(
            select(Prestamo).where(
                Prestamo.activo_id == asset.id,
                Prestamo.estado.in_(OPEN_LOAN_STATES),
            )
        )
        if asset
        else None
    )
    correct_position = asset is not None and reader.posicion_id == asset.posicion_asignada_id
    validation = (
        "no_aplica"
        if observation.tipo == "INICIO"
        else (
            "desconocido"
            if asset is None
            else "correcto"
            if correct_position
            else "posicion_incorrecta"
        )
    )
    occurred_at = received_at - timedelta(milliseconds=observation.antiguedad_ms)
    row = Evento(
        dispositivo_id=device.id,
        arranque=boot,
        secuencia=observation.secuencia,
        tipo=observation.tipo,
        lector_id=reader.id if reader else None,
        activo_id=asset.id if asset else None,
        uid_leido=uid,
        prestamo_id=loan.id if loan else None,
        validacion=validation,
        ocurrido_at=occurred_at,
        recibido_at=received_at,
    )
    db.add(row)
    if loan and occurred_at < loan.operacion_iniciada_at:
        return []
    notifications = []
    if loan and observation.tipo == "RETIRADO" and correct_position:
        if loan.estado == "pendiente_retiro":
            loan.estado, loan.retiro_at = "activo", occurred_at
            asset.estado = "prestado"
            notifications.append((loan, {}))
    elif loan and observation.tipo == "DEVUELTO":
        if loan.estado in ("validando_devolucion", "esperando_posicion"):
            if correct_position:
                loan.estado, loan.devolucion_at = "devuelto", occurred_at
                asset.estado = "disponible"
            else:
                loan.estado = "esperando_posicion"
            notifications.append(
                (
                    loan,
                    {
                        "ubicacion_correcta": location_view(asset.posicion),
                        **({"error": "posicion_incorrecta"} if not correct_position else {}),
                    },
                )
            )
    if observation.tipo == "DEVUELTO" and reader:
        # A wrong UID at the expected return position leaves the operation open.
        waiting = db.scalars(
            select(Prestamo)
            .join(Activo)
            .where(
                Prestamo.estado.in_(("validando_devolucion", "esperando_posicion")),
                Activo.posicion_asignada_id == reader.posicion_id,
                Prestamo.activo_id != (asset.id if asset else -1),
                Prestamo.operacion_iniciada_at <= occurred_at,
            )
        )
        notifications.extend((pending, {"error": "rfid_incorrecto"}) for pending in waiting)
    return notifications


@devices.post("/{dispositivo_id}/eventos", status_code=202, response_model=BatchResult)
def ingest(data: Lote, db: Db, device: Device):
    # Serializes retries for this device, including concurrent duplicate batches.
    db.execute(select(Dispositivo.id).where(Dispositivo.id == device.id).with_for_update())
    readers = {
        r.canal: r
        for r in db.scalars(
            select(Lector).where(
                Lector.dispositivo_id == device.id,
            )
        )
    }
    now = datetime.now(UTC)
    for observation in data.eventos:
        if observation.tipo != "INICIO" and observation.canal not in readers:
            raise HTTPException(422, "Reader is not registered for this device")
        try:
            now - timedelta(milliseconds=observation.antiguedad_ms)
        except (OverflowError, ValueError):
            raise HTTPException(422, "Observation time is outside the supported range") from None
    accepted = duplicates = 0
    notifications = []
    for observation in data.eventos:
        exists = db.scalar(
            select(Evento.id).where(
                Evento.dispositivo_id == device.id,
                Evento.arranque == data.arranque,
                Evento.secuencia == observation.secuencia,
            )
        )
        if exists is not None:
            duplicates += 1
            continue
        notifications.extend(
            process_observation(
                db,
                device,
                data.arranque,
                observation,
                readers.get(observation.canal),
                now,
            )
        )
        db.flush()
        accepted += 1
    save(db)
    for loan, detail in notifications:
        notify_loan(loan, detail)
    return {"aceptados": accepted, "duplicados": duplicates}
