"""Selective E2E acceptance checks against a real local Uvicorn process and PostgreSQL."""

import asyncio
import json
import math
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import httpx2
import pytest
from sqlalchemy import text
from websockets.asyncio.client import connect

from app.database import engine
from tests.conftest import token


@pytest.fixture
def running_api():
    assert engine.url.database.endswith("_test")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    with tempfile.TemporaryFile(mode="w+t") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--fd",
                str(listener.fileno()),
                "--log-level",
                "warning",
            ],
            pass_fds=(listener.fileno(),),
            stdout=log,
            stderr=log,
            env=os.environ.copy(),
        )
        listener.close()
        base = f"http://127.0.0.1:{port}"
        try:
            with httpx2.Client(base_url=base, timeout=5, trust_env=False) as http:
                deadline = time.monotonic() + 10
                while True:
                    try:
                        if http.get("/api/health/ready").status_code == 200:
                            break
                    except httpx2.TransportError:
                        pass
                    if process.poll() is not None or time.monotonic() >= deadline:
                        log.seek(0)
                        pytest.fail(f"Isolated API did not become ready: {log.read()}")
                    threading.Event().wait(
                        0.05
                    )  # Bounded readiness polling, not state synchronization.
                yield http, f"ws://127.0.0.1:{port}"
        finally:
            process.terminate()
            process.wait(timeout=10)


def test_fifty_users_search_and_prepare_loans_under_http_latency_target(running_api):
    http, _ = running_api
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO usuario (id,rol_id,nombre) SELECT n,r.id,'User '||n "
                "FROM generate_series(100,149) n CROSS JOIN rol r WHERE r.nombre='usuario'"
            )
        )
        db.execute(
            text(
                "INSERT INTO activo (id,categoria_id,posicion_asignada_id,nombre,rfid_uid,estado) "
                "SELECT n,1,1,'Camera '||n,lpad(upper(to_hex(n+1000)),8,'0'),'disponible' "
                "FROM generate_series(100,149) n"
            )
        )
    barrier = threading.Barrier(50)

    def operate(identity):
        headers = {"Authorization": f"Bearer {token(identity)}"}
        barrier.wait(timeout=10)
        started = time.perf_counter()
        found = http.get("/api/activos?q=Camera", headers=headers)
        search_seconds = time.perf_counter() - started
        started = time.perf_counter()
        prepared = http.post(
            "/api/prestamos",
            headers=headers,
            json={
                "activo_id": identity,
                "responsable_id": identity,
                "devolucion_esperada_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            },
        )
        return (
            found.status_code,
            prepared.status_code,
            [search_seconds, time.perf_counter() - started],
        )

    with ThreadPoolExecutor(max_workers=50) as pool:
        outcomes = list(pool.map(operate, range(100, 150)))
    assert all(search == 200 and loan == 201 for search, loan, _ in outcomes)
    durations = sorted(duration for _, _, samples in outcomes for duration in samples)
    p95 = durations[math.ceil(len(durations) * 0.95) - 1]
    search_samples = sorted(samples[0] for _, _, samples in outcomes)
    loan_samples = sorted(samples[1] for _, _, samples in outcomes)
    print(
        f"HTTP detail: search_p95_ms={search_samples[47] * 1000:.1f} "
        f"loan_p95_ms={loan_samples[47] * 1000:.1f}"
    )
    print(f"RNF-01: users=50 requests=100 p95_ms={p95 * 1000:.1f}")
    assert p95 < 0.5
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM prestamo")) == 50


def test_fifty_websockets_receive_confirmed_change_without_private_loan_leak(
    running_api, client, headers, device
):
    http, ws_base = running_api
    prepared = http.post(
        "/api/prestamos",
        headers=headers,
        json={
            "activo_id": 1,
            "responsable_id": 3,
            "devolucion_esperada_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    assert prepared.status_code == 201
    loan_id = prepared.json()["id"]

    async def scenario():
        sockets = await asyncio.gather(
            *[
                connect(
                    f"{ws_base}/api/ws/estado",
                    additional_headers={
                        "Authorization": f"Bearer {token(3 if i < 25 else 4)}",
                    },
                )
                for i in range(50)
            ]
        )
        try:
            started = time.perf_counter()
            response = await asyncio.to_thread(
                http.post,
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
                    ],
                },
            )
            assert response.status_code == 202

            async def received(index, ws):
                payload = json.loads(await asyncio.wait_for(ws.recv(), timeout=1))
                elapsed = time.perf_counter() - started
                assert payload["activo_id"] == 1
                if index < 25:
                    assert payload["prestamo_id"] == loan_id and payload["estado"] == "activo"
                else:
                    assert payload["tipo"] == "inventario_actualizado"
                    assert payload["prestamo_id"] is None
                return elapsed

            elapsed = await asyncio.gather(*[received(i, ws) for i, ws in enumerate(sockets)])
            print(f"RNF-02: clients=50 max_ms={max(elapsed) * 1000:.1f}")
            assert max(elapsed) < 1
        finally:
            await asyncio.gather(*[ws.close() for ws in sockets])

    asyncio.run(scenario())


def test_websocket_closes_when_its_access_token_expires(running_api):
    _, ws_base = running_api

    async def scenario():
        expires = datetime.now(UTC) + timedelta(seconds=2)
        async with connect(
            f"{ws_base}/api/ws/estado",
            additional_headers={
                "Authorization": f"Bearer {token(exp=expires)}",
            },
        ) as ws:
            await asyncio.wait_for(ws.wait_closed(), timeout=3)
            assert ws.close_code == 1008

    asyncio.run(scenario())


def test_ten_readers_emit_one_event_per_second_without_drops(running_api, admin):
    http, _ = running_api
    devices = []
    for index in range(10):
        identity = f"load-{index}"
        registered = http.post("/api/dispositivos", headers=admin, json={"id": identity})
        assert registered.status_code == 201
        devices.append((identity, {"X-Device-Key": registered.json()["api_key"]}))
        assert (
            http.post(
                "/api/lectores",
                headers=admin,
                json={
                    "dispositivo_id": identity,
                    "canal": 1,
                    "posicion_id": 1,
                },
            ).status_code
            == 201
        )
    barrier = threading.Barrier(10)

    def send(reader):
        identity, key = reader
        barrier.wait(timeout=10)
        started = time.monotonic()
        responses = []
        for sequence in range(1, 6):
            remaining = started + sequence - 1 - time.monotonic()
            if remaining > 0:
                threading.Event().wait(remaining)  # Defines the required 1 event/s stimulus.
            responses.append(
                http.post(
                    f"/api/dispositivos/{identity}/eventos",
                    headers=key,
                    json={
                        "arranque": 1,
                        "eventos": [
                            {
                                "secuencia": sequence,
                                "tipo": "PRESENTE",
                                "canal": 1,
                                "uid": "DEADBEEF",
                                "antiguedad_ms": 0,
                            }
                        ],
                    },
                )
            )
        return responses

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(send, devices))
    assert all(
        r.status_code == 202 and r.json() == {"aceptados": 1, "duplicados": 0}
        for reader in results
        for r in reader
    )
    with engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM evento")) == 50
    print("RNF-03: readers=10 rate=1event/s/reader samples=50 persisted=50 drops=0")
