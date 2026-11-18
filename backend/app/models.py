"""Persistence model for the documented PostgreSQL schema."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Rol(Base):
    __tablename__ = "rol"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(30), unique=True)


class Usuario(Base):
    __tablename__ = "usuario"
    __table_args__ = (
        UniqueConstraint("credencial_uid", name="uq_usuario_credencial"),
        UniqueConstraint(
            "identificador_institucional_hash", name="uq_usuario_identificador_institucional"
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    rol_id: Mapped[int] = mapped_column(ForeignKey("rol.id"))
    nombre: Mapped[str] = mapped_column(String(150))
    correo: Mapped[str | None] = mapped_column(Text)
    credencial_uid: Mapped[str | None] = mapped_column(Text)
    identificador_institucional_hash: Mapped[str | None] = mapped_column(Text)
    clave_hash: Mapped[str | None] = mapped_column(Text)
    consentimiento_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activo: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    rol: Mapped[Rol] = relationship(lazy="joined")


class Auditoria(Base):
    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    accion: Mapped[str] = mapped_column(String(80))
    entidad: Mapped[str] = mapped_column(String(50))
    entidad_id: Mapped[str] = mapped_column(String(64))
    creado_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Categoria(Base):
    __tablename__ = "categoria"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True)


class Espacio(Base):
    __tablename__ = "espacio"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))


class Gabinete(Base):
    __tablename__ = "gabinete"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    espacio_id: Mapped[int] = mapped_column(ForeignKey("espacio.id"))
    nombre: Mapped[str] = mapped_column(String(120))
    espacio: Mapped[Espacio] = relationship(lazy="joined")


class Posicion(Base):
    __tablename__ = "posicion"
    __table_args__ = (UniqueConstraint("gabinete_id", "estante", "codigo"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    gabinete_id: Mapped[int] = mapped_column(ForeignKey("gabinete.id"))
    estante: Mapped[str] = mapped_column(String(60))
    codigo: Mapped[str] = mapped_column(String(60))
    gabinete: Mapped[Gabinete] = relationship(lazy="joined")


class Activo(Base):
    __tablename__ = "activo"
    __table_args__ = (
        CheckConstraint("estado IN ('disponible','prestado','en_revision')", name="activo_estado"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categoria.id"))
    posicion_asignada_id: Mapped[int] = mapped_column(ForeignKey("posicion.id"))
    nombre: Mapped[str] = mapped_column(String(150))
    rfid_uid: Mapped[str] = mapped_column(String(20), unique=True)
    condicion: Mapped[str | None] = mapped_column(String(100))
    ultima_revision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(30))
    presente: Mapped[bool | None] = mapped_column(Boolean)
    presencia_actualizada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    categoria: Mapped[Categoria] = relationship(lazy="joined")
    posicion: Mapped[Posicion] = relationship(lazy="joined")


OPEN_LOAN_STATES = (
    "pendiente_retiro",
    "activo",
    "validando_devolucion",
    "esperando_posicion",
)


class Prestamo(Base):
    __tablename__ = "prestamo"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('pendiente_retiro','activo','validando_devolucion',"
            "'esperando_posicion','devuelto','cancelado')",
            name="prestamo_estado",
        ),
        Index(
            "uq_prestamo_abierto_activo",
            "activo_id",
            unique=True,
            postgresql_where=text("estado NOT IN ('devuelto','cancelado')"),
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    activo_id: Mapped[int] = mapped_column(ForeignKey("activo.id"))
    responsable_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    entregado_por_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    retiro_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    devolucion_esperada_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    devolucion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    operacion_iniciada_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(30))
    activo: Mapped[Activo] = relationship(lazy="joined")
    responsable: Mapped[Usuario] = relationship(foreign_keys=[responsable_id], lazy="joined")
    entregado_por: Mapped[Usuario] = relationship(foreign_keys=[entregado_por_id], lazy="joined")


class Dispositivo(Base):
    __tablename__ = "dispositivo"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    api_key_hash: Mapped[str] = mapped_column(Text)
    firmware: Mapped[str | None] = mapped_column(String(32))
    ultimo_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_rssi: Mapped[int | None] = mapped_column(Integer)


class Lector(Base):
    __tablename__ = "lector"
    __table_args__ = (UniqueConstraint("dispositivo_id", "canal"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dispositivo_id: Mapped[str] = mapped_column(ForeignKey("dispositivo.id"))
    canal: Mapped[int] = mapped_column(Integer)
    posicion_id: Mapped[int] = mapped_column(ForeignKey("posicion.id"))
    senal_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posicion: Mapped[Posicion] = relationship(lazy="joined")


class Evento(Base):
    __tablename__ = "evento"
    __table_args__ = (UniqueConstraint("dispositivo_id", "arranque", "secuencia"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dispositivo_id: Mapped[str] = mapped_column(ForeignKey("dispositivo.id"))
    lector_id: Mapped[int | None] = mapped_column(ForeignKey("lector.id"))
    activo_id: Mapped[int | None] = mapped_column(ForeignKey("activo.id"))
    prestamo_id: Mapped[int | None] = mapped_column(ForeignKey("prestamo.id"))
    uid_leido: Mapped[str | None] = mapped_column(String(20))
    tipo: Mapped[str] = mapped_column(String(24))
    validacion: Mapped[str | None] = mapped_column(String(24))
    arranque: Mapped[int] = mapped_column(BigInteger)
    secuencia: Mapped[int] = mapped_column(BigInteger)
    ocurrido_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recibido_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lector: Mapped[Lector | None] = relationship(lazy="joined")


class WebhookSuscripcion(Base):
    __tablename__ = "webhook_suscripcion"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    url: Mapped[str] = mapped_column(Text)
    eventos: Mapped[str] = mapped_column(Text)
    secreto_hash: Mapped[str] = mapped_column(Text)
