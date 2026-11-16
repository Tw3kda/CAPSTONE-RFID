import pytest
from sqlalchemy import text

from app.database import engine
from tests.test_loans_devices import event, prepare


@pytest.mark.parametrize("resource", ["espacios", "gabinetes", "dispositivos", "lectores"])
def test_admin_can_list_provisioning_records_without_exposing_device_credentials(
    client, admin, manager, headers, device, resource
):
    assert client.get(f"/api/{resource}").status_code == 401
    assert client.get(f"/api/{resource}", headers=headers).status_code == 403
    assert client.get(f"/api/{resource}", headers=manager).status_code == 403
    listed = client.get(f"/api/{resource}", headers=admin)
    assert listed.status_code == 200
    records = listed.json()
    if resource == "espacios":
        assert records == [{"id": 1, "nombre": "Laboratorio"}]
    elif resource == "gabinetes":
        assert records == [{"id": 1, "nombre": "Gabinete A", "espacio_id": 1}]
    elif resource == "lectores":
        assert records == [
            {"id": 1, "dispositivo_id": "esp-test", "canal": 1, "posicion_id": 1},
            {"id": 2, "dispositivo_id": "esp-test", "canal": 2, "posicion_id": 2},
            {"id": 3, "dispositivo_id": "esp-test", "canal": 3, "posicion_id": 3},
        ]
    else:
        assert records == [
            {
                "id": "esp-test",
                "firmware": None,
                "ultimo_heartbeat": None,
                "ultimo_rssi": None,
            }
        ]
        assert "api_key" not in records[0] and "api_key_hash" not in records[0]
        assert device["X-Device-Key"] not in listed.text


def test_asset_reads_support_category_editing_without_exposing_rfid_uid(client, headers, admin):
    for auth in (headers, admin):
        detail = client.get("/api/activos/1", headers=auth).json()
        listed = client.get("/api/activos?q=ACT-001", headers=auth).json()[0]
        for asset in (detail, listed):
            assert asset["categoria_id"] == 1
            assert asset["categoria"] == "Cámaras"
            assert "rfid_uid" not in asset


def test_partial_asset_edits_preserve_omitted_fields_and_can_replace_known_uid(client, admin):
    renamed = client.patch("/api/activos/1", headers=admin, json={"nombre": "Cámara renombrada"})
    assert renamed.status_code == 200
    assert renamed.json()["nombre"] == "Cámara renombrada"
    assert renamed.json()["estado"] == "disponible"
    category = client.patch("/api/activos/1", headers=admin, json={"categoria_id": 2})
    assert category.status_code == 200
    assert category.json()["categoria"] == "Audio" and category.json()["categoria_id"] == 2
    changed = client.patch("/api/activos/1", headers=admin, json={"rfid_uid": "aabb1234"})
    assert changed.status_code == 200
    with engine.connect() as db:
        row = db.execute(
            text("SELECT nombre,rfid_uid,posicion_asignada_id FROM activo WHERE id=1")
        ).one()
        assert row.nombre == "Cámara renombrada" and row.rfid_uid == "AABB1234"
        assert row.posicion_asignada_id == 1


@pytest.mark.parametrize("payload", [{}, {"nombre": None}, {"estado": None}, {"rfid_uid": ""}])
def test_partial_asset_edits_reject_empty_or_invalid_values(client, admin, payload):
    response = client.patch("/api/activos/1", headers=admin, json=payload)
    assert response.status_code == 422
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM auditoria")) == 0


def test_partial_edit_keeps_loan_guards_and_allows_nullable_condition(
    client, admin, headers, device
):
    prepare(client, headers)
    event(client, device, "RETIRADO", 1)
    assert (
        client.patch("/api/activos/1", headers=headers, json={"nombre": "Denied"}).status_code
        == 403
    )
    changed = client.patch("/api/activos/1", headers=admin, json={"condicion": "Desgaste leve"})
    assert changed.status_code == 200 and changed.json()["estado"] == "prestado"
    cleared = client.patch("/api/activos/1", headers=admin, json={"condicion": None})
    assert cleared.status_code == 200 and cleared.json()["condicion"] is None
    for payload in (
        {"posicion_asignada_id": 2},
        {"rfid_uid": "ABCDEF12"},
        {"estado": "disponible"},
    ):
        assert client.patch("/api/activos/1", headers=admin, json=payload).status_code == 409
    assert (
        client.patch("/api/activos/1", headers=admin, json={"categoria_id": 999}).status_code == 404
    )


def test_staff_can_find_exact_registered_credential_without_revealing_it(
    client, admin, manager, headers
):
    created = client.post(
        "/api/usuarios",
        headers=admin,
        json={
            "nombre": "Synthetic Person",
            "rol": "usuario",
            "credencial": "SYNTHETIC-SEARCH-42",
            "identificador_institucional": "SYNTHETIC-SEARCH-ID-42",
        },
    )
    assert created.status_code == 201
    found = client.get("/api/usuarios", headers=manager, params={"q": "SYNTHETIC-SEARCH-42"})
    assert found.status_code == 200
    assert found.json() == [created.json()]
    assert "SYNTHETIC-SEARCH-42" not in found.text and "credencial_uid" not in found.text
    assert client.get("/api/usuarios?q=SYNTHETIC-SEARCH", headers=manager).json() == []
    assert client.get("/api/usuarios?q=Synthetic", headers=manager).json() == [created.json()]
    assert client.get("/api/usuarios?q=SYNTHETIC-SEARCH-42", headers=headers).status_code == 403


def test_registered_institutional_id_is_distinct_from_qr_searchable_and_admin_managed(
    client, admin, manager, headers
):
    created = client.post(
        "/api/usuarios",
        headers=admin,
        json={
            "nombre": "Synthetic Identity",
            "rol": "usuario",
            "credencial": "SYNTHETIC-QR-77",
            "identificador_institucional": "SYNTHETIC-ID-77",
        },
    )
    assert created.status_code == 201
    identity = created.json()["id"]
    assert "identificador_institucional" not in created.json()
    assert (
        client.post(
            "/api/usuarios",
            headers=admin,
            json={
                "nombre": "Duplicate QR",
                "rol": "usuario",
                "credencial": "SYNTHETIC-QR-77",
                "identificador_institucional": "SYNTHETIC-DIFFERENT-ID",
            },
        ).status_code
        == 409
    )
    for method, value, expected in (
        ("qr", "SYNTHETIC-QR-77", 200),
        ("id", "SYNTHETIC-ID-77", 200),
        ("id", "SYNTHETIC-QR-77", 401),
        ("qr", "SYNTHETIC-ID-77", 401),
    ):
        assert (
            client.post("/api/auth/login", json={"metodo": method, "credencial": value}).status_code
            == expected
        )
    found = client.get("/api/usuarios?q=SYNTHETIC-ID-77", headers=manager)
    assert found.json() == [created.json()]
    assert "SYNTHETIC-ID-77" not in found.text
    with engine.connect() as db:
        stored = db.scalar(
            text("SELECT identificador_institucional_hash FROM usuario WHERE id=:id"),
            {"id": identity},
        )
        assert stored and "SYNTHETIC-ID-77" not in stored
    assert (
        client.post(
            "/api/usuarios",
            headers=admin,
            json={
                "nombre": "Duplicate",
                "rol": "usuario",
                "identificador_institucional": "SYNTHETIC-ID-77",
            },
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/usuarios/{identity}",
            headers=headers,
            json={
                "identificador_institucional": "SYNTHETIC-ID-78",
            },
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/usuarios/{identity}",
            headers=admin,
            json={
                "identificador_institucional": "SYNTHETIC-ID-78",
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/login", json={"metodo": "id", "credencial": "SYNTHETIC-ID-77"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login", json={"metodo": "id", "credencial": "SYNTHETIC-ID-78"}
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/usuarios/{identity}",
            headers=admin,
            json={
                "identificador_institucional": None,
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/auth/login", json={"metodo": "id", "credencial": "SYNTHETIC-ID-78"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/login", json={"metodo": "qr", "credencial": "SYNTHETIC-QR-77"}
        ).status_code
        == 200
    )


def test_new_user_requires_institutional_id_and_can_have_no_qr(client, admin):
    for payload in (
        {"nombre": "Missing", "rol": "usuario"},
        {"nombre": "QR only", "rol": "usuario", "credencial": "SYNTHETIC-QR-ONLY"},
        {"nombre": "Null ID", "rol": "usuario", "identificador_institucional": None},
    ):
        assert client.post("/api/usuarios", headers=admin, json=payload).status_code == 422
    created = client.post(
        "/api/usuarios",
        headers=admin,
        json={
            "nombre": "ID only",
            "rol": "usuario",
            "identificador_institucional": "SYNTHETIC-ID-ONLY",
        },
    )
    assert created.status_code == 201
    assert (
        client.post(
            "/api/auth/login", json={"metodo": "id", "credencial": "SYNTHETIC-ID-ONLY"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/login", json={"metodo": "qr", "credencial": "SYNTHETIC-ID-ONLY"}
        ).status_code
        == 401
    )


def test_admin_can_register_or_remove_optional_qr_without_changing_institutional_id(client, admin):
    created = client.post(
        "/api/usuarios",
        headers=admin,
        json={
            "nombre": "Optional QR",
            "rol": "usuario",
            "identificador_institucional": "SYNTHETIC-OPTIONAL-ID",
        },
    )
    assert created.status_code == 201
    identity = created.json()["id"]
    assert (
        client.patch(
            f"/api/usuarios/{identity}",
            headers=admin,
            json={
                "credencial": "SYNTHETIC-OPTIONAL-QR",
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/login", json={"metodo": "qr", "credencial": "SYNTHETIC-OPTIONAL-QR"}
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/usuarios/{identity}", headers=admin, json={"credencial": None}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/login", json={"metodo": "qr", "credencial": "SYNTHETIC-OPTIONAL-QR"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login", json={"metodo": "id", "credencial": "SYNTHETIC-OPTIONAL-ID"}
        ).status_code
        == 200
    )
