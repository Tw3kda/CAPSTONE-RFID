from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.database import engine
from tests.conftest import token


def event(client, device, kind, sequence, uid="AABBCCDD", channel=1, boot=1, age=0):
    data = {"secuencia": sequence, "tipo": kind, "antiguedad_ms": age}
    if kind != "INICIO":
        data.update(uid=uid, canal=channel)
    return client.post(
        "/api/dispositivos/esp-test/eventos",
        headers=device,
        json={
            "arranque": boot,
            "eventos": [data],
        },
    )


def prepare(client, headers, asset=1, responsible=3):
    return client.post(
        "/api/prestamos",
        headers=headers,
        json={
            "activo_id": asset,
            "responsable_id": responsible,
            "devolucion_esperada_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )


def test_admin_provisions_spaces_cabinets_devices_and_protects_key(client, admin, headers):
    for path, payload in (
        ("espacios", {"nombre": "Estudio"}),
        ("gabinetes", {"nombre": "Armario", "espacio_id": 1}),
        ("dispositivos", {"id": "esp-two"}),
    ):
        assert client.post(f"/api/{path}", headers=headers, json=payload).status_code == 403
        created = client.post(f"/api/{path}", headers=admin, json=payload)
        assert created.status_code == 201
        if path == "dispositivos":
            key = created.json()["api_key"]
            with engine.connect() as db:
                stored = db.scalar(text("SELECT api_key_hash FROM dispositivo WHERE id='esp-two'"))
                assert stored and key not in stored
    assert (
        client.post("/api/dispositivos", headers=admin, json={"id": "esp-two"}).status_code == 409
    )


def test_device_auth_mapping_many_assets_per_position_signal_and_heartbeat(
    client, admin, headers, device
):
    base = "/api/dispositivos/esp-test"
    assert client.get(f"{base}/configuracion").status_code == 401
    assert client.get(f"{base}/configuracion", headers={"X-Device-Key": "bad"}).status_code == 401
    assert client.get("/api/dispositivos/other/configuracion", headers=device).status_code == 401
    mapping = client.get(f"{base}/configuracion", headers=device)
    assert mapping.status_code == 200
    assert mapping.json() == [
        {"uid": "AABBCCDD", "activo_id": 1, "codigo": "ACT-001", "canal": 1},
        {"uid": "11223344", "activo_id": 2, "codigo": "ACT-002", "canal": 1},
        {"uid": "55667788", "activo_id": 3, "codigo": "ACT-003", "canal": 3},
    ]
    assert client.get(f"{base}/senales", headers=device).json() == {"canales": []}
    assert client.post("/api/activos/1/senal", headers=headers).status_code == 202
    assert client.get(f"{base}/senales", headers=device).json() == {"canales": [1]}
    with engine.begin() as db:
        db.execute(text("UPDATE lector SET senal_hasta=now()-interval '1 second'"))
    assert client.get(f"{base}/senales", headers=device).json() == {"canales": []}
    assert (
        client.post(
            f"{base}/heartbeat",
            headers=device,
            json={
                "arranque": 1,
                "firmware": "1.0-test",
                "rssi": -65,
            },
        ).status_code
        == 204
    )
    with engine.connect() as db:
        row = db.execute(
            text("SELECT firmware,ultimo_rssi,ultimo_heartbeat FROM dispositivo")
        ).one()
        assert row.firmware == "1.0-test" and row.ultimo_rssi == -65 and row.ultimo_heartbeat
    assert (
        client.patch("/api/lectores/1", headers=headers, json={"posicion_id": 2}).status_code == 403
    )
    assert (
        client.patch("/api/lectores/1", headers=admin, json={"posicion_id": 2}).status_code == 200
    )
    assert client.get(f"{base}/configuracion", headers=device).json() == [
        {"uid": "55667788", "activo_id": 3, "codigo": "ACT-003", "canal": 3},
    ]


def test_loan_requires_responsibility_delivery_date_availability_and_staff_delegation(
    client, headers, manager
):
    assert prepare(client, {}, responsible=3).status_code == 401
    assert prepare(client, headers, responsible=4).status_code == 403
    assert prepare(client, headers, asset=3).status_code == 409
    assert prepare(client, headers, asset=999).status_code == 404
    assert (
        client.post(
            "/api/prestamos",
            headers=headers,
            json={
                "activo_id": 1,
                "responsable_id": 3,
                "devolucion_esperada_at": "2020-01-01T00:00:00Z",
            },
        ).status_code
        == 422
    )
    loan = prepare(client, manager, responsible=4)
    assert loan.status_code == 201
    data = loan.json()
    assert data["estado"] == "pendiente_retiro"
    assert data["retiro_at"] is None
    assert data["responsable_id"] == 4 and data["entregado_por_id"] == 2
    assert prepare(client, headers).status_code == 409
    assert client.get("/api/activos/1", headers=headers).json()["estado"] == "disponible"


def test_loan_visibility_enforced_in_list_detail_return_and_cancel(client, headers, manager):
    loan = prepare(client, manager, responsible=4).json()
    lid = loan["id"]
    assert client.get("/api/prestamos", headers=headers).json() == []
    assert client.get("/api/prestamos?alcance=todos", headers=headers).status_code == 403
    assert len(client.get("/api/prestamos?alcance=todos", headers=manager).json()) == 1
    assert client.get(f"/api/prestamos/{lid}", headers=headers).status_code == 403
    assert client.post(f"/api/prestamos/{lid}/devolucion", headers=headers).status_code == 403
    assert (
        client.post(f"/api/prestamos/{lid}/cancelar-operacion", headers=headers).status_code == 403
    )
    owner = {"Authorization": f"Bearer {token(4)}"}
    assert client.get(f"/api/prestamos/{lid}", headers=owner).status_code == 200
    assert client.get("/api/prestamos/999", headers=manager).status_code == 404


def test_only_matching_physical_withdrawal_activates_pending_loan(client, headers, device):
    lid = prepare(client, headers).json()["id"]
    assert event(client, device, "INICIO", 1).status_code == 202
    assert event(client, device, "PRESENTE", 2).status_code == 202
    assert event(client, device, "RETIRADO", 3, uid="11223344").status_code == 202
    assert (
        client.get(f"/api/prestamos/{lid}", headers=headers).json()["estado"] == "pendiente_retiro"
    )
    assert event(client, device, "RETIRADO", 4, channel=2).status_code == 202
    assert (
        client.get(f"/api/prestamos/{lid}", headers=headers).json()["estado"] == "pendiente_retiro"
    )
    assert event(client, device, "RETIRADO", 5).json() == {"aceptados": 1, "duplicados": 0}
    loan = client.get(f"/api/prestamos/{lid}", headers=headers).json()
    assert loan["estado"] == "activo" and loan["retiro_at"]
    assert client.get("/api/activos/1", headers=headers).json()["estado"] == "prestado"
    history = client.get("/api/activos/1/historial", headers=headers).json()
    assert history[0]["tipo"] == "RETIRADO" and history[0]["prestamo_id"] == lid


def test_return_wrong_identity_wrong_position_initial_presence_and_correct_position(
    client, headers, device
):
    lid = prepare(client, headers).json()["id"]
    event(client, device, "RETIRADO", 1)
    started = client.post(f"/api/prestamos/{lid}/devolucion", headers=headers)
    assert started.status_code == 202 and started.json()["estado"] == "validando_devolucion"
    event(client, device, "DEVUELTO", 2, uid="11223344")
    assert (
        client.get(f"/api/prestamos/{lid}", headers=headers).json()["estado"]
        == "validando_devolucion"
    )
    event(client, device, "PRESENTE", 3)
    assert (
        client.get(f"/api/prestamos/{lid}", headers=headers).json()["estado"]
        == "validando_devolucion"
    )
    event(client, device, "DEVUELTO", 4, channel=2)
    waiting = client.get(f"/api/prestamos/{lid}", headers=headers).json()
    assert waiting["estado"] == "esperando_posicion" and waiting["devolucion_at"] is None
    assert waiting["ubicacion_asignada"]["posicion_id"] == 1
    event(client, device, "DEVUELTO", 5)
    closed = client.get(f"/api/prestamos/{lid}", headers=headers).json()
    assert closed["estado"] == "devuelto" and closed["devolucion_at"]
    assert client.get("/api/activos/1", headers=headers).json()["estado"] == "disponible"
    assert client.post(f"/api/prestamos/{lid}/devolucion", headers=headers).status_code == 409


def test_cancel_operations_never_invent_physical_confirmation(client, headers, device):
    lid = prepare(client, headers).json()["id"]
    cancelled = client.post(f"/api/prestamos/{lid}/cancelar-operacion", headers=headers)
    assert cancelled.json()["estado"] == "cancelado" and cancelled.json()["retiro_at"] is None
    assert (
        client.post(f"/api/prestamos/{lid}/cancelar-operacion", headers=headers).status_code == 409
    )
    lid = prepare(client, headers).json()["id"]
    event(client, device, "RETIRADO", 1)
    assert (
        client.post(f"/api/prestamos/{lid}/cancelar-operacion", headers=headers).status_code == 409
    )
    client.post(f"/api/prestamos/{lid}/devolucion", headers=headers)
    cancelled = client.post(f"/api/prestamos/{lid}/cancelar-operacion", headers=headers).json()
    assert cancelled["estado"] == "activo" and cancelled["devolucion_at"] is None
    event(client, device, "DEVUELTO", 2)
    assert client.get(f"/api/prestamos/{lid}", headers=headers).json()["estado"] == "activo"


def test_unknown_uid_and_boot_sequence_idempotency_are_persisted(client, headers, device):
    assert event(client, device, "DEVUELTO", 1, uid="DEADBEEF").json() == {
        "aceptados": 1,
        "duplicados": 0,
    }
    assert event(client, device, "DEVUELTO", 1, uid="DEADBEEF").json() == {
        "aceptados": 0,
        "duplicados": 1,
    }
    assert event(client, device, "DEVUELTO", 1, uid="DEADBEEF", boot=2).json() == {
        "aceptados": 1,
        "duplicados": 0,
    }
    with engine.connect() as db:
        rows = db.execute(text("SELECT activo_id,uid_leido,validacion FROM evento")).all()
        assert len(rows) == 2
        assert all(
            r.activo_id is None and r.uid_leido == "DEADBEEF" and r.validacion == "desconocido"
            for r in rows
        )


@pytest.mark.parametrize(
    "invalid",
    [
        {"secuencia": 2, "tipo": "DEVUELTO", "canal": 99, "uid": "AABBCCDD", "antiguedad_ms": 0},
        {"secuencia": 2, "tipo": "DEVUELTO", "canal": 1, "uid": "invalid", "antiguedad_ms": 0},
        {"secuencia": 2, "tipo": "INICIO", "canal": 1, "uid": "AABBCCDD", "antiguedad_ms": 0},
        {"secuencia": 2, "tipo": "RETIRADO", "antiguedad_ms": 0},
    ],
)
def test_invalid_batch_is_atomic_including_loan_state(client, headers, device, invalid):
    lid = prepare(client, headers).json()["id"]
    response = client.post(
        "/api/dispositivos/esp-test/eventos",
        headers=device,
        json={
            "arranque": 1,
            "eventos": [
                {
                    "secuencia": 1,
                    "tipo": "RETIRADO",
                    "canal": 1,
                    "uid": "AABBCCDD",
                    "antiguedad_ms": 0,
                },
                invalid,
            ],
        },
    )
    assert response.status_code == 422
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM evento")) == 0
    assert (
        client.get(f"/api/prestamos/{lid}", headers=headers).json()["estado"] == "pendiente_retiro"
    )


def test_assets_with_open_loan_cannot_be_administratively_remapped_or_falsely_marked_available(
    client, headers, admin, device
):
    prepare(client, headers)
    payload = {
        "nombre": "Cámara",
        "categoria_id": 1,
        "posicion_asignada_id": 2,
        "rfid_uid": "AABBCCDD",
    }
    assert client.patch("/api/activos/1", headers=admin, json=payload).status_code == 409
    event(client, device, "RETIRADO", 1)
    payload.update(posicion_asignada_id=1, estado="disponible")
    assert client.patch("/api/activos/1", headers=admin, json=payload).status_code == 409


def test_delayed_events_cannot_confirm_operations_started_after_the_observation(
    client, headers, device
):
    lid = prepare(client, headers).json()["id"]
    assert event(client, device, "RETIRADO", 1, age=3600000).status_code == 202
    assert (
        client.get(f"/api/prestamos/{lid}", headers=headers).json()["estado"] == "pendiente_retiro"
    )
    event(client, device, "RETIRADO", 2)
    client.post(f"/api/prestamos/{lid}/devolucion", headers=headers)
    event(client, device, "DEVUELTO", 3, age=3600000)
    assert (
        client.get(f"/api/prestamos/{lid}", headers=headers).json()["estado"]
        == "validando_devolucion"
    )
    client.post(f"/api/prestamos/{lid}/cancelar-operacion", headers=headers)
    client.post(f"/api/prestamos/{lid}/devolucion", headers=headers)
    event(client, device, "DEVUELTO", 4, age=3600000)
    assert (
        client.get(f"/api/prestamos/{lid}", headers=headers).json()["estado"]
        == "validando_devolucion"
    )
    event(client, device, "DEVUELTO", 5)
    assert client.get(f"/api/prestamos/{lid}", headers=headers).json()["estado"] == "devuelto"
