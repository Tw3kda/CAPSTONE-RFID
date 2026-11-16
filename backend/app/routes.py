from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from app.config import get_settings
from app.models import Activo, Categoria, Evento, Gabinete, Lector, Posicion, Rol, Usuario
from app.realtime import notify_inventory
from app.schemas import (
    ActivoEdicion,
    ActivoOut,
    AssetState,
    CategoriaOut,
    LectorEdicion,
    LectorNuevo,
    LectorOut,
    Login,
    Movimiento,
    Nombre,
    PosicionNueva,
    Refresh,
    Sesion,
    Tokens,
    Ubicacion,
    UbicacionMapa,
    UsuarioEdicion,
    UsuarioNuevo,
    UsuarioOut,
)
from app.security import (
    Admin,
    Db,
    Staff,
    User,
    active_user,
    credential_digest,
    decode_token,
    protect,
    session_tokens,
)
from app.services import (
    asset_view,
    audit,
    get_or_404,
    location_view,
    save,
    search_assets,
    user_view,
)

auth = APIRouter(prefix="/api/auth", tags=["Autenticación"])
inventory = APIRouter(prefix="/api", tags=["Inventario"])
administration = APIRouter(prefix="/api", tags=["Administración"])


def set_session_cookie(response: Response, tokens: dict):
    response.set_cookie(
        "thesora_session",
        tokens["access_token"],
        max_age=get_settings().access_token_seconds,
        httponly=True,
        secure=get_settings().secure_cookies,
        samesite="strict",
        path="/api/ws",
    )


@auth.post("/login", response_model=Sesion)
def login(data: Login, db: Db, response: Response):
    user = db.scalar(
        select(Usuario).where(
            Usuario.credencial_uid == credential_digest(data.credencial),
            Usuario.activo.is_(True),
        )
    )
    if user is None:
        raise HTTPException(401, "Invalid credential")
    tokens = session_tokens(user)
    set_session_cookie(response, tokens)
    return {"tokens": tokens, "usuario": user_view(user)}


@auth.get("/me", response_model=UsuarioOut)
def me(user: User):
    return user_view(user)


@auth.post("/refresh", response_model=Tokens)
def refresh(data: Refresh, db: Db, response: Response):
    tokens = session_tokens(active_user(db, decode_token(data.refresh_token, "refresh")))
    set_session_cookie(response, tokens)
    return tokens


@inventory.get("/categorias", response_model=list[CategoriaOut])
def categories(db: Db, user: User):
    return db.scalars(select(Categoria).order_by(Categoria.id)).all()


@administration.post("/categorias", status_code=201, response_model=CategoriaOut)
def create_category(data: Nombre, db: Db, user: Admin):
    row = Categoria(**data.model_dump())
    db.add(row)
    audit(db, user, "crear_categoria", row)
    save(db)
    notify_inventory()
    return row


@inventory.get("/activos", response_model=list[ActivoOut])
def assets(
    db: Db,
    user: User,
    q: str | None = None,
    categoria_id: int | None = None,
    estado: AssetState | None = None,
):
    return search_assets(db, q, categoria_id, estado)


@inventory.get("/activos/{id}", response_model=ActivoOut)
def asset(id: int, db: Db, user: User):
    return asset_view(get_or_404(db, Activo, id))


def asset_data(data: ActivoEdicion, db: Db) -> dict:
    get_or_404(db, Categoria, data.categoria_id)
    get_or_404(db, Posicion, data.posicion_asignada_id)
    values = data.model_dump(exclude_unset=True)
    values["rfid_uid"] = data.rfid_uid.upper()
    if values.get("estado") is None:
        values["estado"] = "disponible"
    return values


@administration.post("/activos", status_code=201, response_model=ActivoOut)
def create_asset(data: ActivoEdicion, db: Db, user: Admin):
    row = Activo(**asset_data(data, db))
    db.add(row)
    audit(db, user, "crear_activo", row)
    save(db)
    db.refresh(row)
    notify_inventory(row.id)
    return asset_view(row)


@administration.patch("/activos/{id}", response_model=ActivoOut)
def edit_asset(id: int, data: ActivoEdicion, db: Db, user: Admin):
    from app.loans import locked_asset
    from app.models import OPEN_LOAN_STATES, Prestamo

    row = locked_asset(db, id)
    open_loan = db.scalar(
        select(Prestamo.id).where(
            Prestamo.activo_id == id,
            Prestamo.estado.in_(OPEN_LOAN_STATES),
        )
    )
    if open_loan is not None and (
        data.posicion_asignada_id != row.posicion_asignada_id
        or data.rfid_uid.upper() != row.rfid_uid
        or (data.estado is not None and data.estado != row.estado)
    ):
        raise HTTPException(409, "Cannot change physical identity or state during an open loan")
    values = asset_data(data, db)
    if data.estado is None:
        values.pop("estado", None)
    for key, value in values.items():
        setattr(row, key, value)
    audit(db, user, "editar_activo", row)
    save(db)
    db.refresh(row)
    notify_inventory(row.id)
    return asset_view(row)


@inventory.get("/activos/{id}/ubicacion", response_model=UbicacionMapa)
def location(id: int, db: Db, user: User):
    position = get_or_404(db, Activo, id).posicion
    neighbors = db.scalars(
        select(Posicion)
        .where(
            Posicion.gabinete_id == position.gabinete_id,
            Posicion.estante == position.estante,
        )
        .order_by(Posicion.id)
    )
    return {
        "asignada": location_view(position),
        "posiciones_estante": [location_view(p) for p in neighbors],
    }


@inventory.get("/activos/{id}/historial", response_model=list[Movimiento])
def history(id: int, db: Db, user: User):
    get_or_404(db, Activo, id)
    return [
        {
            "id": e.id,
            "tipo": e.tipo,
            "ocurrido_at": e.ocurrido_at,
            "prestamo_id": e.prestamo_id,
            "ubicacion": location_view(e.lector.posicion) if e.lector else None,
        }
        for e in db.scalars(
            select(Evento)
            .where(Evento.activo_id == id)
            .order_by(Evento.ocurrido_at.desc(), Evento.id.desc())
        )
    ]


@inventory.get("/posiciones", response_model=list[Ubicacion])
def positions(db: Db, user: User):
    return [location_view(p) for p in db.scalars(select(Posicion).order_by(Posicion.id))]


@administration.post("/posiciones", status_code=201, response_model=Ubicacion)
def create_position(data: PosicionNueva, db: Db, user: Admin):
    get_or_404(db, Gabinete, data.gabinete_id)
    row = Posicion(**data.model_dump())
    db.add(row)
    audit(db, user, "crear_posicion", row)
    save(db)
    db.refresh(row)
    return location_view(row)


@administration.get("/usuarios", response_model=list[UsuarioOut])
def users(db: Db, user: Staff, q: str | None = None):
    query = select(Usuario)
    if q:
        query = query.where(Usuario.nombre.ilike(f"%{q}%"))
    return [user_view(u) for u in db.scalars(query.order_by(Usuario.id))]


@administration.post("/usuarios", status_code=201, response_model=UsuarioOut)
def create_user(data: UsuarioNuevo, db: Db, user: Admin):
    role = db.scalar(select(Rol).where(Rol.nombre == data.rol))
    row = Usuario(
        nombre=data.nombre,
        rol=role,
        activo=True,
        correo=protect(data.correo),
        credencial_uid=credential_digest(data.credencial),
    )
    db.add(row)
    audit(db, user, "crear_usuario", row)
    save(db)
    return user_view(row)


@administration.patch("/usuarios/{id}", response_model=UsuarioOut)
def edit_user(id: int, data: UsuarioEdicion, db: Db, user: Admin):
    row = get_or_404(db, Usuario, id)
    values = data.model_dump(exclude_unset=True)
    if any(value is None for value in values.values()):
        raise HTTPException(422, "Account fields cannot be null")
    role = values.pop("rol", None)
    if role:
        row.rol = db.scalar(select(Rol).where(Rol.nombre == role))
    for key, value in values.items():
        setattr(row, key, value)
    audit(db, user, "editar_usuario", row)
    save(db)
    return user_view(row)


@administration.post("/lectores", status_code=201, response_model=LectorOut)
def create_reader(data: LectorNuevo, db: Db, user: Admin):
    from app.models import Dispositivo

    get_or_404(db, Dispositivo, data.dispositivo_id)
    get_or_404(db, Posicion, data.posicion_id)
    row = Lector(**data.model_dump())
    db.add(row)
    audit(db, user, "crear_lector", row)
    save(db)
    return row


@administration.patch("/lectores/{id}", response_model=LectorOut)
def edit_reader(id: int, data: LectorEdicion, db: Db, user: Admin):
    row = get_or_404(db, Lector, id)
    get_or_404(db, Posicion, data.posicion_id)
    row.posicion_id = data.posicion_id
    audit(db, user, "editar_lector", row)
    save(db)
    return row
