"""Integration fixtures: real PostgreSQL, real auth and real application dependencies."""

import os
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ["AUTH_SIGNING_KEY"] = "test-only-access-signing-key-at-least-32-characters"
os.environ["DATA_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_data(request):
    if request.module.__name__.endswith("test_schema"):
        yield
        return
    assert engine.url.database.endswith("_test"), "Refusing to truncate a non-test database"
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE evento, prestamo, lector, dispositivo, activo, posicion, gabinete, "
                "espacio, categoria, auditoria, usuario, webhook_suscripcion "
                "RESTART IDENTITY CASCADE"
            )
        )
        connection.execute(
            text(
                "INSERT INTO usuario (id, rol_id, nombre) "
                "SELECT v.id, r.id, v.nombre FROM (VALUES "
                "(1, 'administrador', 'Admin'), (2, 'encargado', 'Encargado'), "
                "(3, 'usuario', 'Ana'), (4, 'usuario', 'Luis')) "
                "AS v(id, rol, nombre) JOIN rol r ON r.nombre=v.rol"
            )
        )
        connection.execute(text("SELECT setval('usuario_id_seq', 4)"))
        connection.execute(text("INSERT INTO categoria (nombre) VALUES ('Cámaras'), ('Audio')"))
        connection.execute(text("INSERT INTO espacio (nombre) VALUES ('Laboratorio')"))
        connection.execute(text("INSERT INTO gabinete (espacio_id,nombre) VALUES (1,'Gabinete A')"))
        connection.execute(
            text(
                "INSERT INTO posicion (gabinete_id,estante,codigo) VALUES "
                "(1,'E1','P1'), (1,'E1','P2'), (1,'E2','P3')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO activo (categoria_id,posicion_asignada_id,nombre,rfid_uid,estado) "
                "VALUES (1,1,'Cámara Sony','AABBCCDD','disponible'), "
                "(2,1,'Micrófono','11223344','disponible'), "
                "(2,3,'Grabadora','55667788','en_revision')"
            )
        )
    yield


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def token(user_id=3, kind="access", **claims):
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "type": kind,
            "iat": now,
            "exp": now + timedelta(minutes=15),
            "iss": "thesora",
            "aud": "thesora-web",
            **claims,
        },
        os.environ["AUTH_SIGNING_KEY"],
        algorithm="HS256",
    )


@pytest.fixture
def headers():
    return {"Authorization": f"Bearer {token()}"}


@pytest.fixture
def admin():
    return {"Authorization": f"Bearer {token(1)}"}


@pytest.fixture
def manager():
    return {"Authorization": f"Bearer {token(2)}"}


@pytest.fixture
def device(client, admin):
    response = client.post("/api/dispositivos", headers=admin, json={"id": "esp-test"})
    assert response.status_code == 201
    key = response.json()["api_key"]
    assert len(key) >= 32
    for channel, position in ((1, 1), (2, 2), (3, 3)):
        registered = client.post(
            "/api/lectores",
            headers=admin,
            json={"dispositivo_id": "esp-test", "canal": channel, "posicion_id": position},
        )
        assert registered.status_code == 201
    return {"X-Device-Key": key}
