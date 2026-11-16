"""Signed sessions, protected personal fields, and per-device authentication."""

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

import jwt
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Usuario

Db = Annotated[Session, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)


def signing_key() -> str:
    secret = get_settings().auth_signing_key
    if secret is None or len(secret.get_secret_value()) < 32:
        raise HTTPException(503, "Authentication is not configured")
    return secret.get_secret_value()


def decode_token(value: str, kind: str = "access") -> int:
    try:
        claims = jwt.decode(
            value,
            signing_key(),
            algorithms=["HS256"],
            issuer="thesora",
            audience="thesora-web",
            options={"require": ["sub", "exp", "iat", "iss", "aud", "type"]},
        )
        if claims["type"] != kind or int(claims["sub"]) < 1:
            raise ValueError
        return int(claims["sub"])
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(
            401, "Invalid session", headers={"WWW-Authenticate": "Bearer"}
        ) from None


def session_tokens(user: Usuario) -> dict:
    settings = get_settings()
    now = datetime.now(UTC)
    result = {"token_type": "bearer", "expires_in": settings.access_token_seconds}
    for kind, seconds in (
        ("access", settings.access_token_seconds),
        ("refresh", settings.refresh_token_seconds),
    ):
        result[f"{kind}_token"] = jwt.encode(
            {
                "sub": str(user.id),
                "type": kind,
                "iat": now,
                "exp": now + timedelta(seconds=seconds),
                "iss": "thesora",
                "aud": "thesora-web",
                "jti": str(uuid4()),
            },
            signing_key(),
            algorithm="HS256",
        )
    return result


def active_user(db: Session, user_id: int) -> Usuario:
    user = db.get(Usuario, user_id)
    if user is None or not user.activo:
        raise HTTPException(401, "Invalid session")
    return user


def current_user(db: Db, auth: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    if auth is None:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    return active_user(db, decode_token(auth.credentials))


User = Annotated[Usuario, Depends(current_user)]


def require_admin(user: User):
    if user.rol.nombre != "administrador":
        raise HTTPException(403, "Administrator required")
    return user


def require_staff(user: User):
    if user.rol.nombre not in ("administrador", "encargado"):
        raise HTTPException(403, "Staff role required")
    return user


Admin = Annotated[Usuario, Depends(require_admin)]
Staff = Annotated[Usuario, Depends(require_staff)]


def personal_cipher() -> Fernet:
    key = get_settings().data_encryption_key
    if key is None:
        raise HTTPException(503, "Personal data protection is not configured")
    try:
        return Fernet(key.get_secret_value().encode())
    except ValueError:
        raise HTTPException(503, "Personal data protection is not configured") from None


def protect(value: str | None) -> str | None:
    return personal_cipher().encrypt(value.encode()).decode() if value is not None else None


def credential_digest(value: str | None) -> str | None:
    if value is None:
        return None
    key = get_settings().data_encryption_key
    if key is None:
        raise HTTPException(503, "Personal data protection is not configured")
    return hmac.new(key.get_secret_value().encode(), value.encode(), hashlib.sha256).hexdigest()
