"""Authenticated, commit-after notification hub for the single API process."""

import asyncio
from dataclasses import dataclass, field

import anyio
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import engine
from app.models import Usuario
from app.security import active_user, decode_token

realtime = APIRouter()


@dataclass(eq=False)
class Subscriber:
    socket: WebSocket
    user_id: int
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class Hub:
    def __init__(self):
        self.subscribers: set[Subscriber] = set()

    def accounts(self):
        identities = {peer.user_id for peer in self.subscribers}
        with Session(engine) as db:
            return {
                u.id: (u.activo, u.rol.nombre)
                for u in db.scalars(select(Usuario).where(Usuario.id.in_(identities)))
            }

    async def publish(self, message: dict, responsible_id: int | None):
        if not self.subscribers:
            return
        accounts = await anyio.to_thread.run_sync(self.accounts)

        async def deliver(peer):
            active, role = accounts.get(peer.user_id, (False, "usuario"))
            try:
                async with peer.lock:
                    if not active:
                        await peer.socket.close(code=1008)
                        self.subscribers.discard(peer)
                    elif (
                        responsible_id is None
                        or peer.user_id == responsible_id
                        or role != "usuario"
                    ):
                        await peer.socket.send_json(message)
            except (WebSocketDisconnect, OSError, RuntimeError):
                self.subscribers.discard(peer)

        async with anyio.create_task_group() as group:
            for peer in tuple(self.subscribers):
                group.start_soon(deliver, peer)


hub = Hub()


def notify(message: dict, responsible_id: int | None = None):
    # Sync FastAPI handlers execute in AnyIO's worker threads.
    anyio.from_thread.run(hub.publish, message, responsible_id)


def notify_loan(loan, detail: dict | None = None):
    notify(
        {
            "tipo": "prestamo_actualizado",
            "activo_id": loan.activo_id,
            "prestamo_id": loan.id,
            "estado": loan.estado,
            "detalle": detail or {},
        },
        loan.responsable_id,
    )


def notify_inventory(asset_id: int | None = None):
    notify(
        {
            "tipo": "inventario_actualizado",
            "activo_id": asset_id,
            "prestamo_id": None,
            "estado": None,
            "detalle": {},
        }
    )


@realtime.websocket("/api/ws/estado")
async def state_socket(socket: WebSocket):
    origin = socket.headers.get("origin")
    if origin is not None and origin not in get_settings().websocket_origins:
        await socket.close(code=1008)
        return
    authorization = socket.headers.get("authorization", "")
    token = authorization[7:] if authorization.lower().startswith("bearer ") else None
    if not token and origin:
        token = socket.cookies.get("thesora_session")
    try:
        if not token or socket.query_params:
            raise HTTPException(401, "Invalid session")
        user_id = decode_token(token)

        def validate_account():
            with Session(engine) as db:
                active_user(db, user_id)

        await anyio.to_thread.run_sync(validate_account)
    except HTTPException:
        await socket.close(code=1008)
        return
    await socket.accept()
    peer = Subscriber(socket=socket, user_id=user_id)
    hub.subscribers.add(peer)
    try:
        while True:
            await socket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.subscribers.discard(peer)
