import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import APIKeyHeader
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
from app.realtime import notify_inventory, notify_loan
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


class DispositivoOut(BaseModel):
    id: str
    firmware: str | None
    ultimo_heartbeat: datetime | None
    ultimo_rssi: int | None


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


@provisioning.get("/espacios", response_model=list[EntityOut])
def list_spaces(db: Db, user: Admin):
    return db.scalars(select(Espacio).order_by(Espacio.id)).all()


@provisioning.get("/gabinetes", response_model=list[GabineteOut])
def list_cabinets(db: Db, user: Admin):
    return db.scalars(select(Gabinete).order_by(Gabinete.id)).all()


@provisioning.get("/dispositivos", response_model=list[DispositivoOut])
def list_devices(db: Db, user: Admin):
    return db.scalars(select(Dispositivo).order_by(Dispositivo.id)).all()


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


device_key = APIKeyHeader(name="X-Device-Key", scheme_name="deviceKey", auto_error=False)


def authenticated_device(
    dispositivo_id: str, db: Db, key: Annotated[str | None, Depends(device_key)] = None
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


def process_observation(db, device, boot, observation, reader, received_at, inventory_changes):
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
    presence_changed = False
    if asset and observation.tipo != "INICIO":
        if asset.presencia_actualizada_at and occurred_at < asset.presencia_actualizada_at:
            # Persist late offline observations without reversing newer physical/business state.
            return []
        present = observation.tipo != "RETIRADO" and correct_position
        presence_changed = asset.presente is not present
        asset.presente, asset.presencia_actualizada_at = present, occurred_at
    if loan and occurred_at < loan.operacion_iniciada_at:
        if presence_changed:
            inventory_changes.append((asset.id, {"presente": asset.presente}))
        return []
    notifications = []
    withdrawal_confirmed = False
    if loan and observation.tipo == "RETIRADO" and correct_position:
        if loan.estado == "pendiente_retiro":
            loan.estado, loan.retiro_at = "activo", occurred_at
            asset.estado = "prestado"
            withdrawal_confirmed = True
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
    if reader and (
        observation.tipo == "DEVUELTO"
        or (observation.tipo == "RETIRADO" and not withdrawal_confirmed)
    ):
        # A shared reader can serve several assets. A valid withdrawal belongs only
        # to its matching loan; an unexpected UID leaves other operations pending.
        waiting_states = (
            ("pendiente_retiro",)
            if observation.tipo == "RETIRADO"
            else ("validando_devolucion", "esperando_posicion")
        )
        waiting = db.scalars(
            select(Prestamo)
            .join(Activo)
            .where(
                Prestamo.estado.in_(waiting_states),
                Activo.posicion_asignada_id == reader.posicion_id,
                Prestamo.activo_id != (asset.id if asset else -1),
                Prestamo.operacion_iniciada_at <= occurred_at,
            )
        )
        notifications.extend((pending, {"error": "rfid_incorrecto"}) for pending in waiting)
    loan_notified = loan is not None and any(pending.id == loan.id for pending, _ in notifications)
    if presence_changed and not loan_notified:
        detail = {"presente": asset.presente}
        if observation.tipo == "RETIRADO" and correct_position and loan is None:
            detail["error"] = "retiro_sin_prestamo"
        inventory_changes.append((asset.id, detail))
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
    inventory_changes = []
    # Offline batches may arrive shuffled. Replay oldest first with sequence as tie breaker.
    for observation in sorted(data.eventos, key=lambda item: (-item.antiguedad_ms, item.secuencia)):
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
                inventory_changes,
            )
        )
        db.flush()
        accepted += 1
    save(db)
    for loan, detail in notifications:
        notify_loan(loan, detail)
    for asset_id, detail in inventory_changes:
        notify_inventory(asset_id, detail)
    return {"aceptados": accepted, "duplicados": duplicates}
