import json
from datetime import UTC, datetime

from sqlalchemy import text

from app.database import engine


def test_recommendations_receive_resource_evidence_even_without_low_use_candidates(
    client, admin, recommendation_provider, monkeypatch
):
    from app import analysis

    now = datetime(2026, 11, 18, 12, tzinfo=UTC)
    monkeypatch.setattr(analysis, "datetime", type("Clock", (), {"now": lambda _: now}))
    with engine.begin() as db:
        db.execute(text("UPDATE activo SET nombre='PRIVATE-INJECTION-TEXT' WHERE id=1"))
        db.execute(text("UPDATE usuario SET nombre='PRIVATE-USER' WHERE id=3"))
        db.execute(
            text("""
            INSERT INTO prestamo (activo_id,responsable_id,entregado_por_id,retiro_at,
                devolucion_esperada_at,devolucion_at,estado,operacion_iniciada_at) VALUES
            (1,3,2,'2026-11-10 10:00Z','2026-11-11Z',
                '2026-11-10 12:00Z','devuelto','2026-11-10 09:00Z'),
            (1,3,2,'2026-11-11 10:00Z','2026-11-12Z',
                '2026-11-11 16:00Z','devuelto','2026-11-11 09:00Z'),
            (1,3,2,'2026-09-29 10:00Z','2026-09-30Z',
                '2026-09-29 20:00Z','devuelto','2026-09-29 09:00Z'),
            (2,3,2,'2026-10-10 10:00Z','2026-10-12Z',
                '2026-10-12 10:00Z','devuelto','2026-10-10 09:00Z'),
            (3,3,2,'2026-11-12 10:00Z','2026-11-13Z',NULL,'activo','2026-11-12 09:00Z'),
            (2,3,2,NULL,'2026-11-13Z',NULL,'cancelado','2026-11-12 09:00Z'),
            (1,3,2,'2026-07-01Z','2026-07-02Z','2026-07-02Z','devuelto','2026-07-01Z')
        """)
        )
        db.execute(
            text("""
            INSERT INTO auditoria (accion,entidad,entidad_id,creado_at)
            SELECT 'historial_demostracion_ia','prestamo',id::text,now()
            FROM prestamo WHERE retiro_at='2026-11-10 10:00Z'
        """)
        )
    calls = []

    # Capture the external HTTP request while retaining the deterministic Responses boundary.
    import urllib.request

    exchange = urllib.request.urlopen

    def capture(request, timeout):
        calls.append(json.loads(request.data))
        return exchange(request, timeout)

    monkeypatch.setattr(urllib.request, "urlopen", capture)
    result = client.post("/api/analisis/recomendacion", headers=admin)
    assert result.status_code == 200
    context = json.loads(calls[0]["input"])
    assert context["total_baja_utilizacion"] == 0
    by_id = {candidate["id"]: candidate for candidate in context["candidatos"]}
    assert set(by_id) == {1, 2, 3}
    first = by_id[1]
    assert first["uso"] == {
        "retiros_90d": 3,
        "retiros_30d": 2,
        "retiros_30d_anteriores": 1,
        "devoluciones_90d": 3,
        "duracion_mediana_horas": 6.0,
        "duracion_maxima_horas": 10.0,
    }
    assert first["disponible"] is True and first["sin_retiros_90d"] is False
    assert by_id[2]["uso"]["duracion_mediana_horas"] == 48.0
    assert by_id[3]["uso"]["devoluciones_90d"] == 0
    assert by_id[3]["uso"]["duracion_mediana_horas"] is None
    serialized = calls[0]["input"]
    for forbidden in (
        "PRIVATE-USER",
        "responsable_id",
        "entregado_por_id",
        "AABBCCDD",
        "uid",
        "correo",
        "devolucion_esperada_at",
        "demostracion",
    ):
        assert forbidden not in serialized
    # Inventory free text is kept as data, never promoted into instructions.
    assert "PRIVATE-INJECTION-TEXT" in serialized
    assert "PRIVATE-INJECTION-TEXT" not in calls[0]["instructions"]
