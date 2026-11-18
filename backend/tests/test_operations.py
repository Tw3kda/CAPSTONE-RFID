import pytest
from sqlalchemy import text

from app.config import get_settings
from app.database import engine


def test_first_admin_bootstrap_is_local_explicit_and_refuses_existing_administration():
    from app.cli import bootstrap_admin

    with pytest.raises(ValueError):
        bootstrap_admin("Initial Admin", "SYNTHETIC-BOOTSTRAP-42", "SyntheticKey42")
    with engine.begin() as db:
        db.execute(text("DELETE FROM usuario"))
    with pytest.raises(ValueError):
        bootstrap_admin("Initial Admin", "", "SyntheticKey42")
    user_id = bootstrap_admin("Initial Admin", "SYNTHETIC-BOOTSTRAP-42", "SyntheticKey42")
    with engine.connect() as db:
        row = db.execute(
            text(
                "SELECT u.nombre,r.nombre AS rol,u.credencial_uid,"
                "u.identificador_institucional_hash FROM usuario u "
                "JOIN rol r ON r.id=u.rol_id WHERE u.id=:id"
            ),
            {"id": user_id},
        ).one()
        assert row.nombre == "Initial Admin" and row.rol == "administrador"
        assert row.credencial_uid is None
        assert row.identificador_institucional_hash
        assert "SYNTHETIC-BOOTSTRAP-42" not in row.identificador_institucional_hash
        assert (
            db.scalar(text("SELECT count(*) FROM auditoria WHERE accion='bootstrap_administrador'"))
            == 1
        )


def test_institutional_retention_hold_blocks_deletion(monkeypatch):
    from app.retention import purge_expired

    monkeypatch.setenv("RETENTION_HOLD", "true")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError):
            purge_expired(dry_run=False)
        assert purge_expired(dry_run=True) == {"prestamos": 0, "eventos": 0, "auditoria": 0}
    finally:
        monkeypatch.delenv("RETENTION_HOLD")
        get_settings.cache_clear()
