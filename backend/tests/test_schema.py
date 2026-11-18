from sqlalchemy import inspect, text

from app.database import engine


def test_migration_creates_authoritative_business_tables():
    expected = {
        "rol",
        "usuario",
        "auditoria",
        "categoria",
        "espacio",
        "gabinete",
        "posicion",
        "activo",
        "prestamo",
        "dispositivo",
        "lector",
        "evento",
        "webhook_suscripcion",
    }
    assert expected <= set(inspect(engine).get_table_names())


def test_migration_provisions_only_the_three_documented_roles():
    with engine.connect() as connection:
        assert set(connection.scalars(text("SELECT nombre FROM rol"))) == {
            "usuario",
            "encargado",
            "administrador",
        }


def test_audit_entity_identifiers_support_string_device_ids():
    columns = {c["name"]: c["type"] for c in inspect(engine).get_columns("auditoria")}
    assert str(columns["entidad_id"]) == "VARCHAR(64)"
