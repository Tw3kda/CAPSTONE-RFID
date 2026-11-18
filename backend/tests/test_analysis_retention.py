from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.database import engine


@pytest.mark.parametrize(
    "method,path", [("GET", "resumen"), ("GET", "reutilizables"), ("POST", "recomendacion")]
)
def test_all_analysis_requires_administrator(
    client, headers, manager, admin, recommendation_provider, method, path
):
    url = f"/api/analisis/{path}"
    for nonadmin in (headers, manager):
        assert client.request(method, url, headers=nonadmin).status_code == 403
    assert client.request(method, url).status_code == 401
    assert client.request(method, url, headers=admin).status_code == 200


def test_analysis_uses_confirmed_withdrawals_not_preparations_and_marks_missing_history(
    client, admin, recommendation_provider
):
    summary = client.get("/api/analisis/resumen", headers=admin)
    assert summary.status_code == 200
    data = summary.json()
    assert (data["disponibles"], data["prestados"], data["en_revision"]) == (2, 0, 1)
    assert data["baja_utilizacion"] == [1, 2]
    assert sum(week["movimientos"] for week in data["uso_semanal"]) == 0
    response = client.post("/api/analisis/recomendacion", headers=admin)
    assert response.status_code == 200
    assert response.json()["datos_insuficientes"] is True
    assert response.json()["texto"]
    assert 3 in response.json()["activos_relacionados"]
    for asset_id in response.json()["activos_relacionados"]:
        assert client.get(f"/api/activos/{asset_id}", headers=admin).status_code == 200
    assert client.get("/api/analisis/resumen").status_code == 401
    assert client.get("/api/analisis/reutilizables").status_code == 401
    assert client.post("/api/analisis/recomendacion").status_code == 401


def test_analysis_excludes_old_withdrawals_and_identifies_available_unused_assets(client, admin):
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO prestamo (activo_id,responsable_id,entregado_por_id,retiro_at,"
                "devolucion_esperada_at,devolucion_at,estado,operacion_iniciada_at) VALUES "
                "(1,3,2,now()-interval '95 days',now()-interval '94 days',"
                "now()-interval '94 days','devuelto',now()-interval '96 days'),"
                "(1,3,2,now()-interval '1 day',now()+interval '1 day',now(),'devuelto',"
                "now()-interval '2 days'),"
                "(2,3,2,NULL,now()+interval '1 day',NULL,'cancelado',now())"
            )
        )
    data = client.get("/api/analisis/resumen", headers=admin).json()
    assert sum(week["movimientos"] for week in data["uso_semanal"]) == 1
    assert data["baja_utilizacion"] == [2]
    assert [a["id"] for a in client.get("/api/analisis/reutilizables", headers=admin).json()] == [2]


def test_retention_keeps_recent_records_open_loans_and_linked_events():
    # Protects RNF-12: calendar months for loans/audit, 90 days for unlinked observations.
    from app.retention import purge_expired

    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO prestamo (activo_id,responsable_id,entregado_por_id,retiro_at,"
                "devolucion_esperada_at,devolucion_at,estado,operacion_iniciada_at) VALUES "
                "(1,3,2,'2023-01-01Z','2023-01-02Z','2023-01-02Z','devuelto','2023-01-01Z'),"
                "(1,3,2,'2025-01-01Z','2025-01-02Z','2025-01-02Z','devuelto','2025-01-01Z'),"
                "(2,3,2,'2023-01-01Z','2023-01-02Z',NULL,'activo','2023-01-01Z'),"
                "(1,3,2,'2024-11-15Z','2024-11-16Z','2024-11-16Z','devuelto','2024-11-15Z')"
            )
        )
        db.execute(
            text("INSERT INTO dispositivo (id,api_key_hash) VALUES ('retention','not-plaintext')")
        )
        db.execute(
            text(
                "INSERT INTO evento (dispositivo_id,prestamo_id,tipo,arranque,secuencia,"
                "ocurrido_at,recibido_at) "
                "VALUES ('retention',NULL,'INICIO',1,1,'2025-01-01Z','2025-01-01Z'),"
                "('retention',NULL,'INICIO',1,2,'2026-10-01Z','2026-10-01Z'),"
                "('retention',3,'RETIRADO',1,3,'2023-01-01Z','2023-01-01Z'),"
                "('retention',1,'RETIRADO',1,4,'2023-01-01Z','2023-01-01Z'),"
                "('retention',1,'RETIRADO',1,5,'2026-11-15Z','2026-11-15Z'),"
                "('retention',NULL,'INICIO',1,6,'2026-08-18Z','2026-08-18Z')"
            )
        )
        db.execute(
            text(
                "INSERT INTO auditoria (accion,entidad,entidad_id,creado_at) VALUES "
                "('crear','activo','1','2024-01-01Z'), ('crear','activo','2','2026-10-01Z'),"
                "('crear','activo','3','2025-11-16Z')"
            )
        )
    now = datetime(2026, 11, 16, tzinfo=UTC)
    preview = purge_expired(now=now, dry_run=True)
    assert preview == {"prestamos": 1, "eventos": 2, "auditoria": 1}
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM prestamo")) == 4
    assert purge_expired(now=now, dry_run=False) == preview
    with engine.connect() as db:
        assert set(db.scalars(text("SELECT id FROM prestamo"))) == {2, 3, 4}
        assert set(db.scalars(text("SELECT secuencia FROM evento"))) == {2, 3, 5, 6}
        assert db.scalar(text("SELECT prestamo_id FROM evento WHERE secuencia=5")) is None
        assert (
            db.scalar(text("SELECT count(*) FROM auditoria WHERE creado_at < '2025-11-16Z'")) == 0
        )


def test_retention_calendar_months_preserve_leap_day_semantics():
    from app.retention import months_before

    assert months_before(datetime(2024, 2, 29, tzinfo=UTC), 12) == datetime(2023, 2, 28, tzinfo=UTC)
