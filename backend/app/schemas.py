from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

RoleName = Literal["usuario", "encargado", "administrador"]
AssetState = Literal["disponible", "prestado", "en_revision"]
Nonempty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
UID = Annotated[str, StringConstraints(pattern=r"^[0-9A-Fa-f]{8,20}$")]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Nombre(Input):
    nombre: Nonempty = Field(max_length=100)


class CategoriaOut(BaseModel):
    id: int
    nombre: str


class UsuarioOut(BaseModel):
    id: int
    nombre: str
    rol: RoleName
    activo: bool


class UsuarioNuevo(Input):
    nombre: Nonempty = Field(max_length=150)
    rol: RoleName
    correo: str | None = Field(default=None, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    credencial: Nonempty | None = Field(default=None, max_length=256)


class UsuarioEdicion(Input):
    nombre: Nonempty | None = Field(default=None, max_length=150)
    rol: RoleName | None = None
    activo: bool | None = None


class Ubicacion(BaseModel):
    posicion_id: int
    espacio: str
    gabinete: str
    estante: str
    codigo: str


class UbicacionMapa(BaseModel):
    asignada: Ubicacion
    posiciones_estante: list[Ubicacion]


class ActivoEdicion(Input):
    nombre: Nonempty = Field(max_length=150)
    categoria_id: int = Field(gt=0)
    posicion_asignada_id: int = Field(gt=0)
    rfid_uid: UID
    estado: AssetState | None = None
    condicion: str | None = Field(default=None, max_length=100)
    ultima_revision_at: AwareDatetime | None = None


class ActivoOut(BaseModel):
    id: int
    nombre: str
    codigo: str
    categoria: str
    estado: AssetState
    condicion: str | None = None
    ultima_revision_at: datetime | None = None
    ubicacion: Ubicacion


class PosicionNueva(Input):
    gabinete_id: int = Field(gt=0)
    estante: Nonempty = Field(max_length=60)
    codigo: Nonempty = Field(max_length=60)


class LectorNuevo(Input):
    dispositivo_id: Nonempty = Field(max_length=64)
    canal: int = Field(ge=1)
    posicion_id: int = Field(gt=0)


class LectorEdicion(Input):
    posicion_id: int = Field(gt=0)


class LectorOut(BaseModel):
    id: int
    dispositivo_id: str
    canal: int
    posicion_id: int


class Movimiento(BaseModel):
    id: int
    tipo: str
    ocurrido_at: datetime
    prestamo_id: int | None = None
    ubicacion: Ubicacion | None = None


class Refresh(Input):
    refresh_token: str


class Login(Input):
    metodo: Literal["qr", "id"]
    credencial: Nonempty = Field(max_length=256)


class Tokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class Sesion(BaseModel):
    tokens: Tokens
    usuario: UsuarioOut
