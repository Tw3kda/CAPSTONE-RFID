from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import or_, select

from app.config import get_settings
from app.models import Activo, Categoria, Evento, Gabinete, Lector, Posicion, Rol, Usuario
from app.realtime import notify_inventory
from app.schemas import (
    ActivoEdicion,
    ActivoOut,
    ActivoParcial,
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
    card_identity,
    credential_digest,
    decode_token,
    password_hash,
    protect,
    registered_card_digest,
    session_tokens,
    verify_password,
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
    query = select(Usuario).where(Usuario.activo.is_(True))
    if data.metodo == "qr":
        try:
            identifier, canonical = card_identity(data.credencial)
        except ValueError:
            raise HTTPException(401, "Invalid credential") from None
        query = query.where(
            Usuario.identificador_institucional_hash == credential_digest(identifier),
            # Exact full-card hashes are supported only during explicit legacy re-binding.
            Usuario.credencial_uid.in_(
                [credential_digest(canonical), credential_digest(data.credencial)]
            ),
        )
    else:
        query = query.where(
            Usuario.identificador_institucional_hash == credential_digest(data.credencial)
        )
    user = db.scalar(query)
    if user is None or (
        data.metodo == "id" and not verify_password(data.clave.get_secret_value(), user.clave_hash)
    ):
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


def asset_data(data: ActivoEdicion | ActivoParcial, db: Db) -> dict:
    values = data.model_dump(exclude_unset=True)
    if "categoria_id" in values:
        get_or_404(db, Categoria, values["categoria_id"])
    if "posicion_asignada_id" in values:
        get_or_404(db, Posicion, values["posicion_asignada_id"])
    if "rfid_uid" in values:
        values["rfid_uid"] = values["rfid_uid"].upper()
    return values


@administration.post("/activos", status_code=201, response_model=ActivoOut)
def create_asset(data: ActivoEdicion, db: Db, user: Admin):
    values = asset_data(data, db)
    if values.get("estado") is None:
        values["estado"] = "disponible"
    row = Activo(**values)
    db.add(row)
    audit(db, user, "crear_activo", row)
    save(db)
    db.refresh(row)
    notify_inventory(row.id)
    return asset_view(row)


@administration.patch("/activos/{id}", response_model=ActivoOut)
def edit_asset(id: int, data: ActivoParcial, db: Db, user: Admin):
    from app.loans import locked_asset
    from app.models import OPEN_LOAN_STATES, Prestamo

    row = locked_asset(db, id)
    open_loan = db.scalar(
        select(Prestamo.id).where(
            Prestamo.activo_id == id,
            Prestamo.estado.in_(OPEN_LOAN_STATES),
        )
    )
    values = asset_data(data, db)
    if open_loan is not None and any(
        key in values and values[key] != getattr(row, key)
        for key in ("posicion_asignada_id", "rfid_uid", "estado")
    ):
        raise HTTPException(409, "Cannot change physical identity or state during an open loan")
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
        digest = credential_digest(q)
        card_digests = [digest]
        try:
            card_digests.append(credential_digest(card_identity(q)[1]))
        except ValueError:
            pass
        query = query.where(
            or_(
                Usuario.nombre.ilike(f"%{q}%"),
                Usuario.credencial_uid.in_(card_digests),
                Usuario.identificador_institucional_hash == digest,
            )
        )
    return [user_view(u) for u in db.scalars(query.order_by(Usuario.id))]


@administration.post("/usuarios", status_code=201, response_model=UsuarioOut)
def create_user(data: UsuarioNuevo, db: Db, user: Admin):
    role = db.scalar(select(Rol).where(Rol.nombre == data.rol))
    identifier_hash = credential_digest(data.identificador_institucional)
    row = Usuario(
        nombre=data.nombre,
        rol=role,
        activo=True,
        correo=protect(data.correo),
        credencial_uid=registered_card_digest(data.credencial, identifier_hash),
        identificador_institucional_hash=identifier_hash,
        clave_hash=password_hash(data.clave.get_secret_value()),
    )
    db.add(row)
    audit(db, user, "crear_usuario", row)
    save(db)
    return user_view(row)


@administration.patch("/usuarios/{id}", response_model=UsuarioOut)
def edit_user(id: int, data: UsuarioEdicion, db: Db, user: Admin):
    row = get_or_404(db, Usuario, id)
    values = data.model_dump(exclude_unset=True)
    identifier = values.pop("identificador_institucional", None)
    if identifier is not None:
        row.identificador_institucional_hash = credential_digest(identifier)
    if "credencial" in values:
        row.credencial_uid = registered_card_digest(
            values.pop("credencial"), row.identificador_institucional_hash
        )
    elif identifier is not None and row.credencial_uid is not None:
        # Preserve the explicit card binding when the administrator changes the ID.
        row.credencial_uid = registered_card_digest(
            "E000000000" + identifier + "000000", row.identificador_institucional_hash
        )
    if "clave" in values:
        row.clave_hash = password_hash(values.pop("clave").get_secret_value())
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


@administration.get("/lectores", response_model=list[LectorOut])
def list_readers(db: Db, user: Admin):
    return db.scalars(select(Lector).order_by(Lector.id)).all()


@administration.patch("/lectores/{id}", response_model=LectorOut)
def edit_reader(id: int, data: LectorEdicion, db: Db, user: Admin):
    row = get_or_404(db, Lector, id)
    get_or_404(db, Posicion, data.posicion_id)
    row.posicion_id = data.posicion_id
    audit(db, user, "editar_lector", row)
    save(db)
    return row
