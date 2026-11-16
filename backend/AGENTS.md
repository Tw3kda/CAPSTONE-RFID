
# Backend — Agent Guide

The root `AGENTS.md` also applies.

Backend stack: Python, FastAPI, Pydantic, SQLAlchemy, Alembic and PostgreSQL.

Work within `backend/` and follow the project's existing structure and conventions.

## Sources of Truth

Consult only the documentation relevant to the task:

- Functional requirements: `docs/01-requirements/functional.md`
- Non-functional requirements: `docs/01-requirements/non-functional.md`
- Database model: `docs/02-architecture/schema.dbml`
- API contract: `docs/03-api/openapi.yaml`
- Backend testing policy: `backend/tests/TESTING.md`

All paths are relative to the repository root.

Requirements and contracts define expected behavior. Do not derive business rules from implementation details or introduce undocumented functionality.

## Implementation

- Organize related endpoints with FastAPI `APIRouter`.
- Use FastAPI dependency injection for shared dependencies.
- Use Pydantic for request validation and response schemas.
- Keep route handlers focused on HTTP concerns. Place meaningful business logic in testable functions or services.
- Use SQLAlchemy for persistence and Alembic for database migrations.
- Keep transaction boundaries explicit and preserve data integrity.
- Follow the project's established synchronous or asynchronous patterns consistently.
- Prefer straightforward solutions over unnecessary layers, abstractions or dependencies.
- Keep authorization, validation and business rule enforcement authoritative in the backend.

## Contracts and Database Changes

- Implement endpoints according to `docs/03-api/openapi.yaml`.
- Keep database models aligned with `docs/02-architecture/schema.dbml`.
- Use Alembic migrations for schema changes.
- Review generated migrations before applying them, especially destructive operations.
- Update affected contracts and documentation when an intentional change modifies their behavior or structure.
- Do not silently diverge from documented requirements or contracts.

## Testing

Follow `backend/tests/TESTING.md`.

- Use TDD for behavioral changes and bug fixes.
- Use pytest with FastAPI TestClient or HTTPX for API tests.
- Prefer meaningful integration tests for behavior involving multiple application components.
- Use unit tests for isolated logic.
- Mock external boundaries when necessary, preserving real internal collaboration wherever practical.
- Keep tests deterministic and focused on observable behavior.
- Never weaken regression or contract tests merely to make an implementation pass.

## Development and Verification

- Use the dependency manager and commands established in the repository.
- Keep development, testing and production environments isolated.
- Apply migrations through a single designated deployment process.
- Run relevant tests and checks before reporting completion.
- Report verification results and unresolved issues without claiming unexecuted checks.
