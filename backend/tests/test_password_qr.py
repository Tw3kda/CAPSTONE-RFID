"""Authentication requirements: ID plus password, dynamic registered card without password."""

import pytest
from sqlalchemy import text

from app.database import engine
from tests.test_loans_devices import prepare

PASSWORD = "SyntheticKey42"
REPLACEMENT = "ReplacementKey57"
PREFIX = "E000000000"


def card(identifier="730123", suffix="A1B2C3"):
    return PREFIX + identifier + suffix


def registration(identifier="730123", **changes):
    return {
        "nombre": "Synthetic card holder",
        "rol": "usuario",
        "identificador_institucional": identifier,
        "credencial": card(identifier),
        "clave": PASSWORD,
        **changes,
    }


def login(client, method, credential, **extra):
    return client.post(
        "/api/auth/login", json={"metodo": method, "credencial": credential, **extra}
    )


def test_new_accounts_require_password_and_validation_does_not_echo_secrets(client, admin):
    missing = registration()
    missing.pop("clave")
    assert client.post("/api/usuarios", headers=admin, json=missing).status_code == 422
    for secret in ("shortSecret", "x" * 129):
        rejected = client.post("/api/usuarios", headers=admin, json=registration(clave=secret))
        assert rejected.status_code == 422
        assert secret not in rejected.text


def test_id_requires_password_but_two_dynamic_qr_suffixes_need_no_password(client, admin):
    created = client.post("/api/usuarios", headers=admin, json=registration())
    assert created.status_code == 201
    expected = created.json()
    assert login(client, "id", "730123").status_code == 422
    assert login(client, "id", "730123", clave="IncorrectKey57").status_code == 401
    assert login(client, "id", "730123", clave=PASSWORD).json()["usuario"] == expected
    for suffix in ("A1B2C3", "8E8C2A"):
        result = login(client, "qr", card(suffix=suffix))
        assert result.status_code == 200
        assert result.json()["usuario"] == expected
    assert login(client, "qr", card(), clave=PASSWORD).status_code == 422
    assert PASSWORD not in created.text and "clave_hash" not in created.text


def test_password_hashes_are_salted_argon2id_and_never_returned(client, admin):
    for identifier in ("730123", "730124"):
        assert (
            client.post("/api/usuarios", headers=admin, json=registration(identifier)).status_code
            == 201
        )
    with engine.connect() as db:
        hashes = db.scalars(
            text("SELECT clave_hash FROM usuario WHERE clave_hash IS NOT NULL")
        ).all()
        assert len(hashes) == 2 and hashes[0] != hashes[1]
        assert all(value.startswith("$argon2id$v=19$m=19456,t=2,p=1$") for value in hashes)
        assert all(PASSWORD not in value for value in hashes)
    listed = client.get("/api/usuarios", headers=admin)
    assert PASSWORD not in listed.text and "clave" not in listed.text
    assert all(value not in listed.text for value in hashes)


def test_legacy_account_without_password_remains_qr_only_and_inactive_is_rejected(client, admin):
    created = client.post("/api/usuarios", headers=admin, json=registration())
    assert created.status_code == 201
    uid = created.json()["id"]
    with engine.begin() as db:
        db.execute(text("UPDATE usuario SET clave_hash=NULL WHERE id=:id"), {"id": uid})
    assert login(client, "id", "730123", clave=PASSWORD).status_code == 401
    assert login(client, "qr", card()).status_code == 200
    client.patch(f"/api/usuarios/{uid}", headers=admin, json={"activo": False})
    assert login(client, "qr", card()).status_code == 401
    assert login(client, "id", "730123", clave=PASSWORD).status_code == 401


def test_admin_password_reset_preserves_omitted_secret_and_never_accepts_null(
    client, admin, manager
):
    created = client.post("/api/usuarios", headers=admin, json=registration())
    assert created.status_code == 201
    path = f"/api/usuarios/{created.json()['id']}"
    assert client.patch(path, headers=manager, json={"clave": REPLACEMENT}).status_code == 403
    assert client.patch(path, headers=admin, json={"nombre": "Renamed"}).status_code == 200
    assert login(client, "id", "730123", clave=PASSWORD).status_code == 200
    for invalid in (None, "", "short"):
        assert client.patch(path, headers=admin, json={"clave": invalid}).status_code == 422
    changed = client.patch(path, headers=admin, json={"clave": REPLACEMENT})
    assert changed.status_code == 200 and REPLACEMENT not in changed.text
    assert login(client, "id", "730123", clave=PASSWORD).status_code == 401
    assert login(client, "id", "730123", clave=REPLACEMENT).status_code == 200
    assert login(client, "qr", card()).status_code == 200


def test_identifier_change_rebinds_registered_card_without_changing_account_or_loan_fk(
    client, admin, manager
):
    created = client.post("/api/usuarios", headers=admin, json=registration())
    assert created.status_code == 201
    uid = created.json()["id"]
    loan = prepare(client, manager, responsible=uid)
    assert loan.status_code == 201
    changed = client.patch(
        f"/api/usuarios/{uid}", headers=admin, json={"identificador_institucional": "7301237"}
    )
    assert changed.status_code == 200 and changed.json()["id"] == uid
    assert login(client, "qr", card()).status_code == 401
    assert login(client, "qr", card("7301237", "8E8C2A")).json()["usuario"]["id"] == uid
    assert login(client, "id", "7301237", clave=PASSWORD).status_code == 200
    assert (
        client.get(f"/api/prestamos/{loan.json()['id']}", headers=manager).json()["responsable_id"]
        == uid
    )


def test_variable_length_ids_and_prefix_related_accounts_authenticate_exactly(client, admin):
    accounts = {}
    for identifier in ("73", "730123", "7301237"):
        created = client.post("/api/usuarios", headers=admin, json=registration(identifier))
        assert created.status_code == 201
        accounts[identifier] = created.json()["id"]
    for identifier, uid in accounts.items():
        result = login(client, "qr", card(identifier, "8E8C2A"))
        assert result.status_code == 200 and result.json()["usuario"]["id"] == uid


def test_legacy_full_card_can_be_rebound_without_changing_account(client, admin):
    from app.security import credential_digest

    created = client.post("/api/usuarios", headers=admin, json=registration())
    assert created.status_code == 201
    uid = created.json()["id"]
    with engine.begin() as db:
        db.execute(
            text("UPDATE usuario SET credencial_uid=:digest,clave_hash=NULL WHERE id=:id"),
            {"digest": credential_digest(card()), "id": uid},
        )
    assert login(client, "qr", card()).status_code == 200
    assert login(client, "qr", card(suffix="8E8C2A")).status_code == 401
    assert (
        client.patch(f"/api/usuarios/{uid}", headers=admin, json={"credencial": card()}).status_code
        == 200
    )
    assert login(client, "qr", card(suffix="8E8C2A")).json()["usuario"]["id"] == uid


def test_password_whitespace_is_preserved_and_bad_hash_fails_closed(client, admin):
    password = "  SyntheticKey42  "
    created = client.post("/api/usuarios", headers=admin, json=registration(clave=password))
    assert created.status_code == 201
    assert login(client, "id", "730123", clave=password).status_code == 200
    assert login(client, "id", "730123", clave=password.strip()).status_code == 401
    with engine.begin() as db:
        db.execute(
            text("UPDATE usuario SET clave_hash='corrupt' WHERE id=:id"),
            {"id": created.json()["id"]},
        )
    assert login(client, "id", "730123", clave=password).status_code == 401


def test_card_registration_must_match_identifier_and_explicit_binding_is_required(client, admin):
    invalid = client.post(
        "/api/usuarios", headers=admin, json=registration(credencial=card("999123"))
    )
    assert invalid.status_code == 422
    unbound = client.post("/api/usuarios", headers=admin, json=registration(credencial=None))
    assert unbound.status_code == 201
    assert login(client, "qr", card()).status_code == 401
    uid = unbound.json()["id"]
    assert (
        client.patch(f"/api/usuarios/{uid}", headers=admin, json={"credencial": card()}).status_code
        == 200
    )
    assert login(client, "qr", card(suffix="8E8C2A")).status_code == 200
    assert client.post("/api/usuarios", headers=admin, json=registration()).status_code == 409
    assert (
        client.patch(f"/api/usuarios/{uid}", headers=admin, json={"credencial": None}).status_code
        == 200
    )
    assert login(client, "qr", card()).status_code == 401


@pytest.mark.parametrize(
    "credential", ["AABBCCDD", "INVALID730123A1B2C3", PREFIX + "730123", card(suffix="ZZZZZZ")]
)
def test_malformed_or_unregistered_cards_never_authenticate(client, admin, credential):
    assert client.post("/api/usuarios", headers=admin, json=registration()).status_code == 201
    assert login(client, "qr", credential).status_code == 401


def test_id_login_accepts_existing_short_password_but_new_passwords_remain_long(client, admin):
    import base64

    from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
    from sqlalchemy import text

    from app.database import engine
    from app.security import PASSWORD_PREFIX, credential_digest

    salt = b"synthetic-salt!!"
    digest = Argon2id(salt=salt, length=32, iterations=2, lanes=1, memory_cost=19456).derive(
        b"5678"
    )
    encoded = PASSWORD_PREFIX + "$".join(
        base64.b64encode(part).decode().rstrip("=") for part in (salt, digest)
    )
    with engine.begin() as db:
        db.execute(
            text(
                "UPDATE usuario SET identificador_institucional_hash=:identity, "
                "clave_hash=:hash WHERE id=3"
            ),
            {"identity": credential_digest("745678"), "hash": encoded},
        )
    body = {"metodo": "id", "credencial": "745678", "clave": "5678"}
    response = client.post("/api/auth/login", json=body)
    assert response.status_code == 200
    assert response.json()["usuario"]["id"] == 3
    assert client.post("/api/auth/login", json={**body, "clave": "wrong"}).status_code == 401
    for invalid in ("", "x" * 129):
        assert client.post("/api/auth/login", json={**body, "clave": invalid}).status_code == 422
    assert client.patch("/api/usuarios/3", headers=admin, json={"clave": "5678"}).status_code == 422
