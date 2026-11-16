# Backend operations

The API uses Python 3.12, synchronous SQLAlchemy and PostgreSQL 16. Run one Uvicorn
process: the authenticated WebSocket hub is in process. Multiple workers or replicas
require shared notification transport before they are supported.

## Configuration and first administrator

Keep the only `.env` at repository root. Configure `APP_NAME`, database credentials,
`AUTH_SIGNING_KEY` (at least 32 random characters), and `DATA_ENCRYPTION_KEY` (a Fernet
key, generated with `cryptography.fernet.Fernet.generate_key()`). Generate separate
random signing and encryption keys. Preserve the encryption key when data exists:
it protects email ciphertext and credential HMACs. Changing it requires a data migration.
Never expose these values through `VITE_*` variables or version control.

Compose injects only the required configuration. Development allows a non-Secure
WebSocket cookie on loopback HTTP; production always uses Secure cookies over HTTPS.
Access JWTs last 15 minutes and refresh JWTs seven days. Each protected request reloads
the account and role; disabling an account denies both token types and closes its
connected sockets before the next notification. Sockets also close at access expiry.
Refresh renews the WebSocket cookie; reconnect after refreshing. Tokens in WebSocket
URLs are rejected. The browser uses an HttpOnly, SameSite=Strict cookie.

After applying migrations, create the first administrator explicitly from a local shell:

```powershell
docker compose -f docker-compose.dev.yml exec backend python -m app.cli bootstrap-admin --nombre "Administrador"
```

The command prompts for the mandatory institutional ID and optional card QR without echoing
either value. It refuses to run if an
administrator already exists. No default administrator or public registration endpoint
exists. For production use the same command with `docker-compose.yml` from the trusted
deployment shell. Subsequent users and roles are managed through the administrator API.

QR and institutional ID are independent trusted local identifiers, each matched against
its own protected unique registration. Every new user and the bootstrap administrator
must have an institutional ID; the card QR is optional, and registering both is recommended.
Administrators can replace the ID, but cannot clear it. They can register, replace or
explicitly remove a card with `credencial: null`; omitting either field preserves it.
Neither method invokes Microsoft or a second factor. `metodo=id` never falls back to a QR,
and `metodo=qr` never uses the institutional ID. Neither identifier is returned by the API.
The migration leaves the ID column nullable only to preserve legacy users lacking it:
an administrator must register their known institutional ID explicitly, without deriving
it from the QR or inventing a value. New API/CLI accounts cannot omit it.
Copying another person's credential permits identification as that person; this
limitation is accepted for this capstone. Roles always come from the server.

Administrator provisioning screens can list `/api/espacios`, `/api/gabinetes`,
`/api/dispositivos` and `/api/lectores`; these four lists require the administrator role.
The device list returns only ID, firmware, last heartbeat timestamp and RSSI, never a
key or hash. Delegated user search matches names or an exact registered QR/ID without
returning either identifier. The numeric user `id` is internal, not institutional.

Asset reads expose `categoria_id` for category selection, but do not expose RFID UIDs.
An administrator edits only changed fields through partial `PATCH /api/activos/{id}`;
omitted fields are preserved, including the old UID. A new known UID can be supplied to
replace it. Empty/invalid changes are rejected, and open-loan physical identity/state
guards still apply. Nullable condition/review timestamp fields can be cleared explicitly.

## Devices and physical operations

An administrator creates a device with `POST /api/dispositivos`. Its random 256-bit
key is returned once; store it on that ESP32. Only its SHA-256 digest is persisted.
Register each physical channel with `POST /api/lectores` and fetch the current mapping
using that device's `X-Device-Key`. Several assets can share a position. Temporary
locating signals last 30 seconds; the device polls `/senales`.

Preparing a loan does not claim a physical withdrawal. Only `RETIRADO` of the correct
UID at its assigned reader activates it. Starting a return does not close the loan:
`DEVUELTO` of the matching UID at its assigned position closes it. A wrong UID or
position leaves it open and sends the responsible user an error notification. Initial
`PRESENTE` observations never close a loan. Cancelling an operation never invents a
physical confirmation. Queued observations predating the operation are recorded but
cannot confirm it. A partial unique PostgreSQL index prevents concurrent open loans.

Event batches are atomic, limited to eight observations, and idempotent by device,
boot and sequence. Unknown UIDs are recorded. Invalid channels/UIDs invalidate the
whole batch; retries of committed events do not repeat state changes or notifications.
Only the responsible user and staff receive private loan notifications. Other users
receive an inventory invalidation without the loan identifier.

## Retention

Preview ordinary expiry before deleting anything:

```powershell
docker compose -f docker-compose.dev.yml exec -T backend python -m app.cli retention
docker compose -f docker-compose.dev.yml exec -T backend python -m app.cli retention --execute
```

The default is a dry run. The execution is one transaction. Closed loans are retained
24 calendar months, unlinked RFID events 90 days from receipt, and audit records
12 calendar months. Open loans and their linked events survive. Recent events whose
expired loan is removed are preserved and unlinked. Cancelled preparations use their
last operation timestamp for the ordinary 24-month window. Exact cutoffs are retained.
Set `RETENTION_HOLD=true` and recreate the backend when an institutional instruction
or legal hold requires suspending deletion; preview remains available.

Schedule the `retention --execute` command daily through the VPS scheduler after
configuring backups and the applicable institutional retention instruction. This is a
deployment step; the API does not add a background worker or scheduler service.

## Tests and CI

Tests must use a separate PostgreSQL database ending in `_test`. Fixtures refuse to
truncate any other database. Never point tests at production or development data.

```powershell
docker compose -f docker-compose.dev.yml exec -T db sh -c 'createdb -U "$POSTGRES_USER" thesora_test'
docker compose -f docker-compose.dev.yml exec -T -e POSTGRES_DB=thesora_test backend alembic upgrade head
docker compose -f docker-compose.dev.yml exec -T -e POSTGRES_DB=thesora_test backend python -m pytest -q -s
docker compose -f docker-compose.dev.yml exec -T backend python -m ruff check app migrations tests
docker compose -f docker-compose.dev.yml exec -T backend python -m ruff format --check app migrations tests
docker compose -f docker-compose.dev.yml exec -T -e POSTGRES_DB=thesora_test backend alembic check
```

The suite includes real HTTP and WebSocket processes, all authored HTTP operations
and response schemas, role/error paths, concurrent loans/retries, simulated ESP32
traffic, retention and the 50-user/50-socket performance assertions. Performance
thresholds are enforced; an environment that misses RNF-01 fails the suite and CI.
The short reader load check is not a production soak test or physical hardware test.

`.github/workflows/ci.yml` provisions PostgreSQL and runs these checks on pull requests
and pushes to `main`. Configure `Backend CI / backend-checks` as a required repository
status check separately. Local execution does not establish that GitHub CI passed.

Firmware resilience, actual multiple-tag scanning, LEDs and TLS certificate validation
on ESP32 hardware require firmware testing. The historical `webhook_suscripcion`
table is modeled, but no webhook subscription/delivery API is defined by the product
requirements or HTTP contract; no outbound integration is implemented.
