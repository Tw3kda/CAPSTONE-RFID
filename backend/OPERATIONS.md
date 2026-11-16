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

The command prompts for the mandatory institutional ID, a 12–128 character password, and optional
card QR without echoing any of them. It refuses to run if an
administrator already exists. No default administrator or public registration endpoint
exists. For production use the same command with `docker-compose.yml` from the trusted
deployment shell. Subsequent users and roles are managed through the administrator API.

ID login requires both the registered institutional ID and password. Passwords preserve
whitespace and contain 12–128 characters. Every new API/CLI account requires a password;
administrators can reset it using PATCH `clave`, while omission preserves it and null/empty
is rejected. Responses and validation errors never echo passwords or hashes. Argon2id uses
the existing cryptography dependency: 19 MiB, two iterations, one lane, a random 16-byte salt,
and a PHC-encoded result. Comparison uses constant time. See the
[OWASP password storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
and [cryptography Argon2id API](https://cryptography.io/en/44.0.2/hazmat/primitives/key-derivation-functions/#argon2id).

QR login does not accept a password. Complete cards use `E000000000` + a variable-length
numeric institutional ID + exactly six hexadecimal suffix characters. The backend removes
exactly the last six characters, validates the ID against the account's independent HMAC,
and matches the explicitly registered canonical card HMAC. The canonical value alone is not
a login input; the client sends the full scanned card. Suffixes beginning with digits are
handled without a greedy ID extraction. A registered ID alone never grants QR access.
The optional card can be removed with `credencial: null`; omission preserves it. Replacing
an ID also rebinds an existing card to that ID, without changing the account primary key.
Non-numeric institutional IDs can still use ID/password; registering a card requires a
numeric ID. Neither identifier nor its hash is returned. Copying a valid card's stable
identity can impersonate its holder; that QR trust limitation remains accepted. No Microsoft
or additional factor is involved. Roles always come from the server.

Upgrade code and apply Alembic `c8d7e6f5a432` through the designated migration process before
assigning passwords. This additive migration leaves legacy password hashes null and never
invents a password. Such accounts fail closed for ID login. A legacy full-card HMAC can
still authenticate its exact complete card, only when its parsed ID matches the independently
registered ID; arbitrary old credential strings are rejected. An administrator must explicitly
rebind the complete card with PATCH `credencial` to enable changing suffixes. Do not derive
or backfill unknown institutional IDs from stored hashes. Setting passwords and rebinding
production accounts is a separate authorized operation after compatible code is deployed;
a data update cannot activate these behaviors in an old deployment. Preserve all signing,
encryption and device keys, account primary keys and historical references.

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

## OpenAI recommendations

`POST /api/analisis/recomendacion` makes one direct HTTPS request to the OpenAI
Responses API. It uses server-only `OPENAI_API_KEY` from the same root `.env`, and
`OPENAI_MODEL` defaults to `gpt-6.1-terra`. Never put the key in a `VITE_*` variable.
Compose injects these variables only into backend, not migration, database or frontend.
Recreate backend after changing its environment.

The input contains 90-day availability/weekly confirmed-withdrawal aggregates and at
most eight candidates: up to four available low-use assets and four in review. Each
candidate has only ID, name, category, state, condition and last review time. No users,
personal identifiers, individual loans, RFID UIDs, positions or device credentials are
sent. Free text is data in a separate JSON input, never instructions. The backend
selects candidates and computes the insufficient-history flag; AI cannot change states.

The Spanish instructions request reuse before purchasing and technical review before
replacement, without inventing statistics, guaranteeing compatibility or predicting
failures. A strict JSON schema and Pydantic validate the existing response format.
Returned IDs must be a unique subset of candidates, and the history flag must agree.

One explicit generation has a 20-second timeout, `store=false`, low reasoning effort
and at most 1200 output tokens. There are no tools, automatic retries, background jobs,
stored recommendations or heuristic fallback. Missing configuration, timeout, rate
limits or temporary failures return 503. Invalid/refused/incomplete output or an
incompatible provider request returns 502 without provider details. Hiding/reopening
the current result does not generate again; regenerating requires an explicit POST.

The model ID was checked against the actual `/v1/models` catalog for the configured
key. Deterministic tests replace only external HTTPS, retaining routing and PostgreSQL.
A live generation check must use synthetic isolated inventory, never personal QR/IDs.

Primary integration references: [Responses and instructions](https://developers.openai.com/api/docs/guides/text),
[structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[API errors](https://developers.openai.com/api/docs/guides/error-codes),
[server-side keys](https://developers.openai.com/api/docs/guides/production-best-practices),
and the [model catalog](https://developers.openai.com/api/docs/models/gpt-6.1-terra).

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
