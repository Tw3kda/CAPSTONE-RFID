
# Backend Testing Guide

Thesora follows TDD (RED → GREEN → REFACTOR) with a Testing Trophy strategy. Prioritize confidence in required behavior over test count or coverage percentage.

## Sources of Truth

- Requirements: `docs/01-requirements/`
- API: `docs/03-api/openapi.yaml`
- Database: `docs/02-architecture/schema.dbml`
- Existing approved regression tests.

Tests must derive expected behavior from requirements, not from production implementation.

## TDD

1. **RED:** Write a test and verify it fails for the expected behavioral reason.
2. **GREEN:** Implement the smallest change that passes.
3. **REFACTOR:** Improve the code while preserving passing tests.

For non-behavioral changes, use existing checks without creating artificial tests.

## Testing Trophy

- **Static:** Linting, formatting, type checking, OpenAPI and migration validation.
- **Unit:** Isolated algorithms, calculations, parsing and pure business logic.
- **Integration (priority):** Real FastAPI routing, Pydantic validation, dependencies, authentication, SQLAlchemy and PostgreSQL. Use pytest with TestClient or HTTPX.
- **E2E:** Selective tests across running services and real HTTP boundaries.

Choose the cheapest level that adequately protects the behavior. Avoid redundant tests across layers. Acceptance criteria are outcomes to verify, not a separate test category.

## Good Test Practices

- Test observable behavior, not internal implementation.
- Use descriptive names, deterministic inputs and isolated fixtures.
- Assert meaningful outcomes, including relevant errors and edge cases.
- Keep internal collaborators real in integration tests; mock genuine external boundaries.
- Prefer a meaningful integration test over many fragmented unit tests.
- Avoid tautologies, mock-call-only assertions, arbitrary sleeps and implementation-coupled tests.
- Never weaken or delete valid regression tests to obtain green results.
- Use an isolated PostgreSQL test database, never production data.

Every test should answer: **What requirement or material risk does this protect?**

## Verification

Run targeted tests during TDD, neighboring tests after changes and the full suite when warranted. Include relevant static checks.

Do not claim success without observed results.

## GitHub Actions

Maintain CI in `.github/workflows/ci.yml`, triggered by pull requests and pushes to `main`.

CI must:
- Install pinned dependencies and provision test PostgreSQL.
- Run configured static checks and pytest.
- Validate OpenAPI and migrations.
- Fail on any required check failure.

Configure CI as a required status check before merging.

## Reporting

Report checks executed, results and unresolved failures. Do not claim unexecuted verification.
