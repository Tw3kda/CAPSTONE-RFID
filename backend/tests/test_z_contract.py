import re
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate


def contract():
    return yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "docs/03-api/openapi.yaml").read_text(
            encoding="utf-8"
        )
    )


def test_published_openapi_covers_every_documented_operation_and_websocket(client):
    source = contract()
    published = client.get("/api/openapi.json").json()
    validate(source)
    validate(published)
    for path, item in source["paths"].items():
        for method in item.keys() & {"get", "post", "patch", "delete", "put"}:
            assert method in published["paths"].get(f"/api{path}", {}), (method, path)
    assert published["paths"]["/api/dispositivos/{dispositivo_id}/eventos"]["post"]["security"] == [
        {"deviceKey": []}
    ]


def test_contract_success_responses_match_all_http_operations(
    client, headers, admin, manager, device, recommendation_provider
):
    source = contract()
    observed = set()

    def checked(method, path, *, json=None, auth=headers, status=200):
        response = client.request(method, f"/api{path}", headers=auth, json=json)
        assert response.status_code == status, (method, path, response.text)
        template = next(
            key
            for key in source["paths"]
            if re.fullmatch(
                re.sub(r"\{[^}]+\}", "[^/]+", key),
                path,
            )
        )
        operation = source["paths"][template][method.lower()]
        documented = operation["responses"][str(status)]
        schema = documented.get("content", {}).get("application/json", {}).get("schema")
        if schema:
            Draft202012Validator({**schema, "components": source["components"]}).validate(
                response.json()
            )
        observed.add((method.lower(), template))
        return response

    checked("GET", "/health/live", auth={})
    checked("GET", "/health/ready", auth={})
    created = checked(
        "POST",
        "/usuarios",
        auth=admin,
        status=201,
        json={
            "nombre": "Contract",
            "rol": "usuario",
            "credencial": "SYNTHETIC-CONTRACT-42",
            "identificador_institucional": "SYNTHETIC-CONTRACT-ID-42",
        },
    )
    login = checked(
        "POST",
        "/auth/login",
        auth={},
        json={
            "metodo": "qr",
            "credencial": "SYNTHETIC-CONTRACT-42",
        },
    ).json()
    checked(
        "POST", "/auth/refresh", auth={}, json={"refresh_token": login["tokens"]["refresh_token"]}
    )
    checked("GET", "/auth/me")
    checked("GET", "/usuarios", auth=manager)
    checked("PATCH", f"/usuarios/{created.json()['id']}", auth=admin, json={"nombre": "Changed"})
    checked("POST", "/categorias", auth=admin, status=201, json={"nombre": "Contract"})
    checked("GET", "/categorias")
    checked("GET", "/posiciones")
    checked(
        "POST",
        "/posiciones",
        auth=admin,
        status=201,
        json={"gabinete_id": 1, "estante": "E9", "codigo": "P9"},
    )
    checked("POST", "/espacios", auth=admin, status=201, json={"nombre": "Extra"})
    checked("POST", "/gabinetes", auth=admin, status=201, json={"nombre": "Extra", "espacio_id": 1})
    checked("POST", "/dispositivos", auth=admin, status=201, json={"id": "contract-device"})
    for resource in ("espacios", "gabinetes", "dispositivos"):
        checked("GET", f"/{resource}", auth=admin)
    checked(
        "POST",
        "/lectores",
        auth=admin,
        status=201,
        json={"dispositivo_id": "contract-device", "canal": 1, "posicion_id": 2},
    )
    checked("PATCH", "/lectores/4", auth=admin, json={"posicion_id": 3})
    checked("GET", "/lectores", auth=admin)
    asset = {
        "nombre": "Contract asset",
        "categoria_id": 1,
        "posicion_asignada_id": 1,
        "rfid_uid": "ABCDEF01",
    }
    checked("POST", "/activos", auth=admin, status=201, json=asset)
    checked("PATCH", "/activos/4", auth=admin, json=asset)
    for path in ("/activos", "/activos/1", "/activos/1/ubicacion", "/activos/1/historial"):
        checked("GET", path)
    checked("POST", "/activos/1/senal", status=202)
    for suffix in ("configuracion", "senales"):
        checked("GET", f"/dispositivos/esp-test/{suffix}", auth=device)
    checked(
        "POST",
        "/dispositivos/esp-test/heartbeat",
        auth=device,
        status=204,
        json={"arranque": 1, "firmware": "contract"},
    )
    loan = checked(
        "POST",
        "/prestamos",
        status=201,
        json={
            "activo_id": 1,
            "responsable_id": 3,
            "devolucion_esperada_at": "2099-01-01T00:00:00Z",
        },
    ).json()
    checked("GET", "/prestamos")
    checked("GET", f"/prestamos/{loan['id']}")
    checked(
        "POST",
        "/dispositivos/esp-test/eventos",
        auth=device,
        status=202,
        json={
            "arranque": 1,
            "eventos": [
                {
                    "secuencia": 1,
                    "tipo": "RETIRADO",
                    "canal": 1,
                    "uid": "AABBCCDD",
                    "antiguedad_ms": 0,
                }
            ],
        },
    )
    checked("POST", f"/prestamos/{loan['id']}/devolucion", status=202)
    checked("POST", f"/prestamos/{loan['id']}/cancelar-operacion")
    checked("GET", "/activos/1/historial")
    checked("GET", "/analisis/resumen")
    checked("GET", "/analisis/reutilizables")
    checked("POST", "/analisis/recomendacion")
    expected = {
        (method, path)
        for path, item in source["paths"].items()
        for method in item.keys() & {"get", "post", "patch", "delete", "put"}
        if not item.get("get", {}).get("x-websocket")
    }
    assert observed == expected


def test_every_protected_http_operation_rejects_missing_credentials(client):
    source = contract()
    for path, item in source["paths"].items():
        for method in item.keys() & {"get", "post", "patch", "delete", "put"}:
            operation = item[method]
            if operation.get("security") == [] or operation.get("x-websocket"):
                continue
            request_path = path.replace("{id}", "1").replace("{dispositivo_id}", "esp-test")
            response = client.request(method, f"/api{request_path}", json={})
            assert response.status_code == 401, (method, path, response.text)


def test_readiness_reports_real_connection_failure_without_leaking_credentials(client, monkeypatch):
    from sqlalchemy import create_engine

    import app.main
    from app.config import get_settings

    unavailable = create_engine(
        get_settings().database_url.set(host="127.0.0.1", port=1),
        connect_args={"connect_timeout": 1},
    )
    monkeypatch.setattr(app.main, "engine", unavailable)
    try:
        assert client.get("/api/health/live").json() == {"status": "ok"}
        failed = client.get("/api/health/ready")
        assert failed.status_code == 503
        assert failed.json() == {"detail": "Database unavailable"}
    finally:
        unavailable.dispose()
