from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
    model_validator,
)

RoleName = Literal["usuario", "encargado", "administrador"]
AssetState = Literal["disponible", "prestado", "en_revision"]
Nonempty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
UID = Annotated[str, StringConstraints(pattern=r"^[0-9A-Fa-f]{8,20}$")]
Password = Annotated[SecretStr, Field(min_length=12, max_length=128)]


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
    identificador_institucional: Nonempty = Field(max_length=256)
    clave: Password


class UsuarioEdicion(Input):
    nombre: Nonempty | None = Field(default=None, max_length=150)
    rol: RoleName | None = None
    activo: bool | None = None
    identificador_institucional: Nonempty | None = Field(default=None, max_length=256)
    credencial: Nonempty | None = Field(default=None, max_length=256)
    clave: Password | None = None

    @model_validator(mode="after")
    def preserve_required_identifier(self):
        if "clave" in self.model_fields_set and self.clave is None:
            raise ValueError("Password cannot be removed")
        if (
            "identificador_institucional" in self.model_fields_set
            and self.identificador_institucional is None
        ):
            raise ValueError("Institutional identifier cannot be removed")
        return self


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


class ActivoParcial(Input):
    nombre: Nonempty | None = Field(default=None, max_length=150)
    categoria_id: int | None = Field(default=None, gt=0)
    posicion_asignada_id: int | None = Field(default=None, gt=0)
    rfid_uid: UID | None = None
    estado: AssetState | None = None
    condicion: str | None = Field(default=None, max_length=100)
    ultima_revision_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("At least one changed field is required")
        nonnullable = {"nombre", "categoria_id", "posicion_asignada_id", "rfid_uid", "estado"}
        if any(getattr(self, field) is None for field in self.model_fields_set & nonnullable):
            raise ValueError("Asset identity and state fields cannot be null")
        return self


class ActivoOut(BaseModel):
    id: int
    nombre: str
    codigo: str
    categoria: str
    categoria_id: int
    estado: AssetState
    presente: bool | None
    disponible: bool
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
    clave: Password | None = None

    @model_validator(mode="after")
    def method_requires_matching_factors(self):
        if self.metodo == "id" and self.clave is None:
            raise ValueError("ID login requires a password")
        if self.metodo == "qr" and "clave" in self.model_fields_set:
            raise ValueError("QR login does not accept a password")
        return self


class Tokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class Sesion(BaseModel):
    tokens: Tokens
    usuario: UsuarioOut
