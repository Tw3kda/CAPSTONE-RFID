from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.database import engine
from tests.conftest import token


def test_login_trusts_only_registered_active_credential_and_never_client_roles(client, admin):
    payload = {"nombre": "Eva", "rol": "usuario", "credencial": "SYNTHETIC-CREDENTIAL-42"}
    registered = client.post("/api/usuarios", headers=admin, json=payload)
    assert registered.status_code == 201
    for method in ("qr", "id"):
        logged = client.post(
            "/api/auth/login",
            json={
                "metodo": method,
                "credencial": "SYNTHETIC-CREDENTIAL-42",
            },
        )
        assert logged.status_code == 200
        assert logged.json()["usuario"]["id"] == registered.json()["id"]
        assert logged.json()["usuario"]["rol"] == "usuario"
        assert logged.json()["tokens"]["token_type"] == "bearer"
        assert "HttpOnly" in logged.headers["set-cookie"]
    assert (
        client.post("/api/auth/login", json={"metodo": "qr", "credencial": "unknown"}).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json={
                "metodo": "qr",
                "credencial": "SYNTHETIC-CREDENTIAL-42",
                "rol": "administrador",
            },
        ).status_code
        == 422
    )
    assert client.post("/api/usuarios", headers=admin, json=payload).status_code == 409
    client.patch(f"/api/usuarios/{registered.json()['id']}", headers=admin, json={"activo": False})
    assert (
        client.post(
            "/api/auth/login",
            json={
                "metodo": "qr",
                "credencial": "SYNTHETIC-CREDENTIAL-42",
            },
        ).status_code
        == 401
    )


def test_authentication_requires_signed_unexpired_access_and_active_account(client, headers):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer forged"}).status_code == 401
    assert (
        client.get(
            "/api/auth/me",
            headers={
                "Authorization": f"Bearer {token(exp=datetime.now(UTC) - timedelta(seconds=1))}"
            },
        ).status_code
        == 401
    )
    assert (
        client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token(kind='refresh')}"}
        ).status_code
        == 401
    )
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"id": 3, "nombre": "Ana", "rol": "usuario", "activo": True}
    with engine.begin() as db:
        db.execute(text("UPDATE usuario SET activo=false WHERE id=3"))
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_refresh_accepts_only_refresh_tokens_and_rechecks_current_account(client):
    assert client.post("/api/auth/refresh", json={"refresh_token": token()}).status_code == 401
    response = client.post("/api/auth/refresh", json={"refresh_token": token(kind="refresh")})
    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert (
        client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"}
        ).status_code
        == 200
    )
    with engine.begin() as db:
        db.execute(text("UPDATE usuario SET activo=false WHERE id=3"))
    assert (
        client.post("/api/auth/refresh", json={"refresh_token": token(kind="refresh")}).status_code
        == 401
    )


def test_inventory_search_code_category_state_and_location(client, headers):
    assert client.get("/api/activos").status_code == 401
    assert len(client.get("/api/activos", headers=headers).json()) == 3
    for query in ("q=sony", "q=ACT-001", "categoria_id=1"):
        found = client.get(f"/api/activos?{query}", headers=headers)
        assert found.status_code == 200
        assert [a["id"] for a in found.json()] == [1]
    assert len(client.get("/api/activos?estado=disponible", headers=headers).json()) == 2
    asset = client.get("/api/activos/1", headers=headers).json()
    assert asset["codigo"] == "ACT-001"
    assert asset["categoria"] == "Cámaras"
    assert asset["ubicacion"] == {
        "posicion_id": 1,
        "espacio": "Laboratorio",
        "gabinete": "Gabinete A",
        "estante": "E1",
        "codigo": "P1",
    }
    location = client.get("/api/activos/1/ubicacion", headers=headers).json()
    assert location["asignada"] == asset["ubicacion"]
    assert [p["posicion_id"] for p in location["posiciones_estante"]] == [1, 2]
    assert client.get("/api/activos/999", headers=headers).status_code == 404
    assert client.get("/api/activos?estado=invalid", headers=headers).status_code == 422


@pytest.mark.parametrize(
    "path,payload",
    [
        ("categorias", {"nombre": "Lentes"}),
        (
            "activos",
            {
                "nombre": "Lente",
                "categoria_id": 1,
                "posicion_asignada_id": 1,
                "rfid_uid": "AABB1122",
            },
        ),
        ("usuarios", {"nombre": "Eva", "rol": "usuario"}),
        ("posiciones", {"gabinete_id": 1, "estante": "E1", "codigo": "P4"}),
        ("lectores", {"dispositivo_id": "missing", "canal": 1, "posicion_id": 1}),
    ],
)
def test_administration_requires_admin_on_every_creation(client, headers, manager, path, payload):
    assert client.post(f"/api/{path}", json=payload).status_code == 401
    assert client.post(f"/api/{path}", headers=headers, json=payload).status_code == 403
    assert client.post(f"/api/{path}", headers=manager, json=payload).status_code == 403


def test_admin_creates_inventory_and_audits_success_only(client, admin, headers):
    category = client.post("/api/categorias", headers=admin, json={"nombre": "Lentes"})
    assert category.status_code == 201
    assert (
        client.post("/api/categorias", headers=admin, json={"nombre": "Lentes"}).status_code == 409
    )
    position = client.post(
        "/api/posiciones",
        headers=admin,
        json={
            "gabinete_id": 1,
            "estante": "E1",
            "codigo": "P4",
        },
    )
    assert position.status_code == 201
    payload = {
        "nombre": "Lente",
        "categoria_id": category.json()["id"],
        "posicion_asignada_id": position.json()["posicion_id"],
        "rfid_uid": "aabb1122",
    }
    created = client.post("/api/activos", headers=admin, json=payload)
    assert created.status_code == 201
    assert created.json()["estado"] == "disponible"
    assert client.post("/api/activos", headers=admin, json=payload).status_code == 409
    payload["rfid_uid"] = "invalid"
    assert client.post("/api/activos", headers=admin, json=payload).status_code == 422
    assert len(client.get("/api/categorias", headers=headers).json()) == 3
    assert len(client.get("/api/posiciones", headers=headers).json()) == 4
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM auditoria")) == 3
        assert db.scalar(text("SELECT rfid_uid FROM activo WHERE id=4")) == "AABB1122"


def test_admin_can_edit_asset_and_manage_account_roles_with_encrypted_personal_data(
    client, admin, headers, manager
):
    created = client.post(
        "/api/usuarios",
        headers=admin,
        json={
            "nombre": "Eva",
            "rol": "usuario",
            "correo": "eva@example.test",
            "credencial": "INST-EVA",
        },
    )
    assert created.status_code == 201
    user_id = created.json()["id"]
    with engine.connect() as db:
        stored = db.execute(
            text("SELECT correo,credencial_uid FROM usuario WHERE id=:id"), {"id": user_id}
        ).one()
        assert stored.correo and "eva@example.test" not in stored.correo
        assert stored.credencial_uid and "INST-EVA" not in stored.credencial_uid
    assert client.get("/api/usuarios", headers=headers).status_code == 403
    assert [u["id"] for u in client.get("/api/usuarios?q=Eva", headers=manager).json()] == [user_id]
    assert (
        client.patch(
            f"/api/usuarios/{user_id}", headers=headers, json={"rol": "administrador"}
        ).status_code
        == 403
    )
    edited = client.patch(
        f"/api/usuarios/{user_id}", headers=admin, json={"rol": "encargado", "activo": False}
    )
    assert edited.status_code == 200
    assert edited.json()["rol"] == "encargado"
    assert edited.json()["activo"] is False
    payload = {
        "nombre": "Cámara nueva",
        "categoria_id": 1,
        "posicion_asignada_id": 2,
        "rfid_uid": "AABBCCDD",
    }
    assert client.patch("/api/activos/1", headers=headers, json=payload).status_code == 403
    edited_asset = client.patch("/api/activos/1", headers=admin, json=payload)
    assert edited_asset.status_code == 200
    assert edited_asset.json()["ubicacion"]["posicion_id"] == 2
    assert client.get("/api/activos/1/historial", headers=headers).json() == []
