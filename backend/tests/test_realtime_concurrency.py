from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text
from starlette.websockets import WebSocketDisconnect

from app.database import engine
from tests.conftest import token
from tests.test_loans_devices import event, prepare


def test_parallel_preparations_reserve_one_loan_without_partial_writes(client, headers):
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: prepare(client, headers), range(8)))
    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409, 409, 409, 409, 409]
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM prestamo")) == 1


def test_parallel_device_retries_process_physical_event_once(client, headers, device):
    lid = prepare(client, headers).json()["id"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: event(client, device, "RETIRADO", 1), range(8)))
    assert all(r.status_code == 202 for r in responses)
    assert sum(r.json()["aceptados"] for r in responses) == 1
    assert sum(r.json()["duplicados"] for r in responses) == 7
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM evento")) == 1
    assert client.get(f"/api/prestamos/{lid}", headers=headers).json()["estado"] == "activo"


def test_websocket_requires_session_rejects_query_tokens_and_untrusted_origins(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/ws/estado"):
            pass
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/ws/estado?token={token()}"):
            pass
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/api/ws/estado",
            headers={
                "Authorization": f"Bearer {token()}",
                "Origin": "https://untrusted.example",
            },
        ):
            pass


def test_committed_loan_transitions_notify_authorized_websocket_without_reload(
    client, headers, device
):
    with client.websocket_connect("/api/ws/estado", headers=headers) as ws:
        lid = prepare(client, headers).json()["id"]
        prepared = ws.receive_json()
        assert prepared["tipo"] == "prestamo_actualizado"
        assert prepared["prestamo_id"] == lid and prepared["estado"] == "pendiente_retiro"
        event(client, device, "RETIRADO", 1)
        confirmed = ws.receive_json()
        assert confirmed["prestamo_id"] == lid and confirmed["estado"] == "activo"
        assert client.get(f"/api/prestamos/{lid}", headers=headers).json()["retiro_at"]
        client.post(f"/api/prestamos/{lid}/devolucion", headers=headers)
        assert ws.receive_json()["estado"] == "validando_devolucion"
        event(client, device, "DEVUELTO", 2, uid="11223344")
        mismatch = ws.receive_json()
        assert mismatch["prestamo_id"] == lid and mismatch["detalle"]["error"] == "rfid_incorrecto"
        event(client, device, "DEVUELTO", 3, channel=2)
        wrong_position = ws.receive_json()
        assert wrong_position["estado"] == "esperando_posicion"
        assert wrong_position["detalle"]["ubicacion_correcta"]["posicion_id"] == 1
        event(client, device, "DEVUELTO", 4)
        assert ws.receive_json()["estado"] == "devuelto"


def test_websocket_cookie_session_and_revocation_follow_current_account(client, admin):
    client.post(
        "/api/usuarios",
        headers=admin,
        json={
            "nombre": "Socket",
            "rol": "usuario",
            "credencial": "SYNTHETIC-WS-42",
            "identificador_institucional": "SYNTHETIC-WS-ID-42",
        },
    )
    login = client.post("/api/auth/login", json={"metodo": "qr", "credencial": "SYNTHETIC-WS-42"})
    user_id = login.json()["usuario"]["id"]
    cookie = login.headers["set-cookie"].split(";", 1)[0]
    with client.websocket_connect(
        "/api/ws/estado",
        headers={
            "Cookie": cookie,
            "Origin": "https://thesora.redskycol.com",
        },
    ) as ws:
        client.patch(f"/api/usuarios/{user_id}", headers=admin, json={"activo": False})
        # Trigger a public inventory update; the revoked socket must close before receiving it.
        client.post("/api/categorias", headers=admin, json={"nombre": "Nueva"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


@pytest.mark.parametrize("wrong_uid", ["11223344", "DEADBEEF"])
def test_wrong_withdrawal_notifies_only_responsible_and_staff_without_confirming(
    client, headers, manager, admin, device, wrong_uid
):
    lid = prepare(client, headers).json()["id"]
    outsider = {"Authorization": f"Bearer {token(4)}"}
    with (
        client.websocket_connect("/api/ws/estado", headers=headers) as owner,
        client.websocket_connect("/api/ws/estado", headers=manager) as staff,
        client.websocket_connect("/api/ws/estado", headers=outsider) as other,
    ):
        assert event(client, device, "RETIRADO", 1, uid=wrong_uid).status_code == 202
        # A public marker makes absence of a private notification deterministic.
        client.post("/api/categorias", headers=admin, json={"nombre": "Withdrawal marker"})
        for socket in (owner, staff):
            message = socket.receive_json()
            assert message["prestamo_id"] == lid
            assert message["estado"] == "pendiente_retiro"
            assert message["detalle"] == {"error": "rfid_incorrecto"}
            assert socket.receive_json()["tipo"] == "inventario_actualizado"
        assert other.receive_json()["tipo"] == "inventario_actualizado"
        assert client.get(f"/api/prestamos/{lid}", headers=headers).json()["retiro_at"] is None
        with engine.connect() as db:
            observation = db.execute(text("SELECT uid_leido,validacion FROM evento")).one()
            assert observation.uid_leido == wrong_uid
            assert observation.validacion == (
                "desconocido" if wrong_uid == "DEADBEEF" else "correcto"
            )
        assert event(client, device, "RETIRADO", 1, uid=wrong_uid).json()["duplicados"] == 1
        # Correct retry confirms exactly the expected asset; no duplicate error is emitted.
        event(client, device, "RETIRADO", 2)
        for socket in (owner, staff):
            assert socket.receive_json()["estado"] == "activo"
        assert other.receive_json()["tipo"] == "inventario_actualizado"


def test_shared_reader_does_not_report_other_valid_withdrawal_as_wrong_resource(
    client, headers, manager, admin, device
):
    first = prepare(client, headers).json()["id"]
    second = prepare(client, manager, asset=2, responsible=4).json()["id"]
    with client.websocket_connect("/api/ws/estado", headers=headers) as owner:
        event(client, device, "RETIRADO", 1, uid="11223344")
        assert owner.receive_json()["tipo"] == "inventario_actualizado"
        client.post("/api/categorias", headers=admin, json={"nombre": "Shared reader marker"})
        assert owner.receive_json()["tipo"] == "inventario_actualizado"
    assert (
        client.get(f"/api/prestamos/{first}", headers=headers).json()["estado"]
        == "pendiente_retiro"
    )
    assert client.get(f"/api/prestamos/{second}", headers=manager).json()["estado"] == "activo"


def test_admin_nonphysical_asset_edit_preserves_confirmed_loan_state(
    client, headers, admin, device
):
    prepare(client, headers)
    event(client, device, "RETIRADO", 1)
    response = client.patch(
        "/api/activos/1",
        headers=admin,
        json={
            "nombre": "Cámara renombrada",
            "categoria_id": 1,
            "posicion_asignada_id": 1,
            "rfid_uid": "AABBCCDD",
        },
    )
    assert response.status_code == 200
    assert response.json()["estado"] == "prestado"
