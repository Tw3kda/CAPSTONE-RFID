from sqlalchemy import text

from app.database import engine
from tests.test_loans_devices import event, prepare


def test_unregistered_withdrawal_is_unavailable_and_restock_notifies_without_inventing_loan(
    client, headers, admin, device
):
    with client.websocket_connect("/api/ws/estado", headers=headers) as ws:
        assert event(client, device, "RETIRADO", 1).status_code == 202
        asset = client.get("/api/activos/1", headers=headers).json()
        assert asset["disponible"] is False
        assert asset["presente"] is False and asset["estado"] == "disponible"
        assert ws.receive_json() == {
            "tipo": "inventario_actualizado",
            "activo_id": 1,
            "prestamo_id": None,
            "estado": None,
            "detalle": {"error": "retiro_sin_prestamo", "presente": False},
        }
        assert 1 not in [
            a["id"] for a in client.get("/api/activos?estado=disponible", headers=headers).json()
        ]
        assert prepare(client, headers).status_code == 409
        assert client.get("/api/analisis/resumen", headers=admin).json()["disponibles"] == 1
        assert [
            a["id"] for a in client.get("/api/analisis/reutilizables", headers=admin).json()
        ] == [2]
        assert event(client, device, "RETIRADO", 1).json()["duplicados"] == 1
        # A marker proves the duplicate did not emit another notification.
        client.post("/api/categorias", headers=admin, json={"nombre": "After duplicate"})
        assert ws.receive_json()["activo_id"] is None
        assert event(client, device, "DEVUELTO", 2).status_code == 202
        assert ws.receive_json()["detalle"] == {"presente": True}
        restored = client.get("/api/activos/1", headers=headers).json()
        assert restored["presente"] is True and restored["disponible"] is True
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM prestamo")) == 0
        assert db.scalar(text("SELECT count(*) FROM evento")) == 2


def test_presence_preserves_loan_rules_and_ignores_late_observations(client, headers, device):
    lid = prepare(client, headers).json()["id"]
    event(client, device, "RETIRADO", 1)
    asset = client.get("/api/activos/1", headers=headers).json()
    assert asset["presente"] is False and asset["disponible"] is False
    event(client, device, "PRESENTE", 2, age=3600000)
    assert client.get("/api/activos/1", headers=headers).json()["presente"] is False
    # Initial presence is physical inventory, never a business return.
    event(client, device, "PRESENTE", 3)
    assert client.get("/api/activos/1", headers=headers).json()["presente"] is True
    assert client.get("/api/activos/1", headers=headers).json()["disponible"] is False
    assert client.get(f"/api/prestamos/{lid}", headers=headers).json()["estado"] == "activo"
    client.post(f"/api/prestamos/{lid}/devolucion", headers=headers)
    event(client, device, "DEVUELTO", 4, channel=2)
    assert client.get("/api/activos/1", headers=headers).json()["presente"] is False
    assert (
        client.get(f"/api/prestamos/{lid}", headers=headers).json()["estado"]
        == "esperando_posicion"
    )
    event(client, device, "DEVUELTO", 5)
    assert client.get(f"/api/prestamos/{lid}", headers=headers).json()["estado"] == "devuelto"
    assert client.get("/api/activos/1", headers=headers).json()["disponible"] is True
    event(client, device, "RETIRADO", 6, age=7200000)
    assert client.get("/api/activos/1", headers=headers).json()["disponible"] is True


def test_unknown_uid_does_not_change_presence_and_revision_is_not_released(client, headers, device):
    event(client, device, "RETIRADO", 1, uid="DEADBEEF")
    initial = client.get("/api/activos/1", headers=headers).json()
    assert initial["presente"] is None and initial["disponible"] is True
    event(client, device, "PRESENTE", 2, uid="55667788", channel=3)
    revision = client.get("/api/activos/3", headers=headers).json()
    assert revision["presente"] is True and revision["disponible"] is False
    assert revision["estado"] == "en_revision"


def test_shuffled_offline_batch_replays_physical_order(client, headers, device):
    response = client.post(
        "/api/dispositivos/esp-test/eventos",
        headers=device,
        json={
            "arranque": 1,
            "eventos": [
                {
                    "secuencia": 2,
                    "tipo": "RETIRADO",
                    "uid": "AABBCCDD",
                    "canal": 1,
                    "antiguedad_ms": 0,
                },
                {
                    "secuencia": 1,
                    "tipo": "PRESENTE",
                    "uid": "AABBCCDD",
                    "canal": 1,
                    "antiguedad_ms": 1000,
                },
            ],
        },
    )
    assert response.json() == {"aceptados": 2, "duplicados": 0}
    assert client.get("/api/activos/1", headers=headers).json()["disponible"] is False


def test_migration_projects_latest_valid_observation_without_replaying_loans(client, device):
    import importlib

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration = importlib.import_module("migrations.versions.d9e8f7a6b543_asset_physical_presence")
    with engine.begin() as db:
        db.execute(
            text("""
            INSERT INTO evento (dispositivo_id,lector_id,activo_id,uid_leido,tipo,validacion,
                arranque,secuencia,ocurrido_at,recibido_at) VALUES
            ('esp-test',1,1,'AABBCCDD','RETIRADO','correcto',1,2,now(),now()),
            ('esp-test',1,1,'AABBCCDD','PRESENTE','correcto',1,1,now()-interval '1 hour',now()),
            ('esp-test',1,2,'DEADBEEF','PRESENTE','desconocido',1,3,now(),now())
        """)
        )
        with Operations.context(MigrationContext.configure(db)):
            migration.downgrade()
            migration.upgrade()
        assert (
            db.execute(text("SELECT presente,presencia_actualizada_at FROM activo WHERE id=1"))
            .one()
            .presente
            is False
        )
        assert db.scalar(text("SELECT presente FROM activo WHERE id=2")) is None
        assert db.scalar(text("SELECT count(*) FROM prestamo")) == 0
        assert db.scalar(text("SELECT count(*) FROM evento")) == 3
