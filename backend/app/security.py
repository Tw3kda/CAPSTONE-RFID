"""Signed sessions, protected personal fields, and per-device authentication."""

import base64
import binascii
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Usuario

Db = Annotated[Session, Depends(get_db)]
bearer = HTTPBearer(auto_error=False, scheme_name="bearerAuth")


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


PASSWORD_PREFIX = "$argon2id$v=19$m=19456,t=2,p=1$"
CARD_PREFIX = "E000000000"


def password_hash(value: str) -> str:
    if not 12 <= len(value) <= 128:
        raise ValueError("Password must contain 12 to 128 characters")
    salt = secrets.token_bytes(16)
    derived = Argon2id(salt=salt, length=32, iterations=2, lanes=1, memory_cost=19456).derive(
        value.encode()
    )
    encoded = [base64.b64encode(part).decode().rstrip("=") for part in (salt, derived)]
    return PASSWORD_PREFIX + "$".join(encoded)


def verify_password(value: str, encoded: str | None) -> bool:
    if encoded is None or not encoded.startswith(PASSWORD_PREFIX):
        return False
    try:
        parts = encoded[len(PASSWORD_PREFIX) :].split("$")
        if len(parts) != 2:
            return False
        salt, expected = [
            base64.b64decode(part + "=" * (-len(part) % 4), validate=True) for part in parts
        ]
        if len(salt) != 16 or len(expected) != 32:
            return False
        derived = Argon2id(salt=salt, length=32, iterations=2, lanes=1, memory_cost=19456).derive(
            value.encode()
        )
        return hmac.compare_digest(derived, expected)
    except (ValueError, TypeError, binascii.Error):
        return False


def card_identity(value: str) -> tuple[str, str]:
    if not value.startswith(CARD_PREFIX):
        raise ValueError("Invalid card format")
    body = value[len(CARD_PREFIX) :]
    identifier, suffix = body[:-6], body[-6:]
    if (
        not identifier
        or not identifier.isascii()
        or not identifier.isdecimal()
        or len(suffix) != 6
        or any(character not in "0123456789ABCDEFabcdef" for character in suffix)
    ):
        raise ValueError("Invalid card format")
    return identifier, CARD_PREFIX + identifier


def registered_card_digest(value: str | None, identifier_hash: str | None) -> str | None:
    if value is None:
        return None
    try:
        identifier, canonical = card_identity(value)
        if identifier_hash is None or not hmac.compare_digest(
            credential_digest(identifier), identifier_hash
        ):
            raise ValueError("Card identifier does not match the registered account")
    except ValueError:
        raise HTTPException(
            422, "Card must match the registered institutional identifier"
        ) from None
    return credential_digest(canonical)


def credential_digest(value: str | None) -> str | None:
    if value is None:
        return None
    key = get_settings().data_encryption_key
    if key is None:
        raise HTTPException(503, "Personal data protection is not configured")
    return hmac.new(key.get_secret_value().encode(), value.encode(), hashlib.sha256).hexdigest()
