
# Thesora — Agent Guide

Thesora is a university capstone project for tracking shared, individually identifiable equipment using RFID. Implement the documented product with simple, maintainable solutions appropriate to its scope.

## Stack

- Backend: Python 3.12, FastAPI, Pydantic, SQLAlchemy, Alembic.
- Frontend: React + Vite, responsive web application.
- Database: PostgreSQL 16.
- Firmware: ESP32, MFRC522 RFID readers and LEDs.
- Infrastructure: Docker Compose, VPS and Dokploy.
- Public URL: `https://thesora.redskycol.com`.
- API base URL: `https://thesora.redskycol.com/api`.

## Instruction Scope

This `AGENTS.md` applies throughout the repository.

Before working in a subtree, read its instructions:

- Backend → `backend/AGENTS.md`
- Frontend → `frontend/AGENTS.md`
- Cross-cutting work → both files
- Backend testing → `backend/tests/TESTING.md`

More specific instructions take precedence within their scope.

## Sources of Truth

Repository documentation defines expected behavior. Read only the relevant sections.

- Functional requirements: `docs/01-requirements/functional.md`
- Non-functional requirements: `docs/01-requirements/non-functional.md`
- Database model: `docs/02-architecture/schema.dbml`
- API contract: `docs/03-api/openapi.yaml`
- Wireframes and behaviors: `docs/04-frontend/Thesora_Wireframes_Diseno_y_Comportamientos.pdf`
- Brand identity: `docs/04-frontend/Thesora_Manual_de_Marca.pdf`
- Technical design and legal documents: `docs/00-meta/`

The wireframes PDF defines the approved screens and their interactions. Existing frontend mock data and simulated transitions are implementation placeholders, not authoritative behavior.

If authoritative sources conflict, identify the specific conflict before implementing the affected behavior.

## Working Method

- Classify the task and inspect the relevant code and documentation before editing.
- For behavioral changes and bug fixes, follow the TDD cycle guided by `backend/tests/TESTING.md`.
- For visual changes, preserve the approved design and verify the relevant frontend build.
- Keep changes focused on the requested scope.
- Follow existing project conventions unless a change requires otherwise.
- Avoid speculative functionality, unnecessary abstractions, dependencies and unrelated refactors.
- Preserve existing work, including uncommitted changes.
- Do not silently change business rules, API contracts, permissions or database structure.

### Skills

- Use only the skills explicitly instructed by the user or applicable repository instructions.
- Discover and load them using the agent's built-in skill discovery tools.
- If a required skill is unavailable, report it and stop the work that depends on it.
- Skills provide implementation guidance but do not override repository instructions or expand the authorized scope.

## Component Boundaries

### Backend

The backend is authoritative for:

- Authentication and permissions.
- Inventory, assets and physical position mapping.
- Loan and return state transitions.
- RFID event validation, deduplication and persistence.
- Device configuration and synchronization.
- Business rules and data integrity.

### Firmware

The ESP32 handles:

- RFID scanning and presence detection.
- Multiple RFID readers and tags.
- Physical LED signaling.
- Locally cached configuration.
- Offline event buffering and retransmission.
- Heartbeats and device communication.

The backend owns the authoritative configuration and validates reported events. The firmware executes physical operations and retains the local functionality needed during connectivity interruptions.

### Frontend

React consumes the API contract and presents server-confirmed state. It handles user interactions, navigation and presentation without duplicating backend business rules.

## Contracts and Documentation

Keep documentation synchronized with intentional implementation changes.

- API changes → `docs/03-api/openapi.yaml`
- Database changes → SQLAlchemy models, Alembic migrations and `docs/02-architecture/schema.dbml`
- Functional changes → applicable requirements and documented behavior
- Visual changes → preserve the approved wireframes and brand guidelines

Review generated database migrations before applying them.

## Infrastructure

Two Compose configurations are maintained:

- `docker-compose.dev.yml`: local development services; frontend runs separately through Vite.
- `docker-compose.yml`: production deployment through Dokploy, including the built frontend.

Keep environment-specific configuration separated, however only one .env file should be used.

Use environment variables for secrets and credentials. Keep database connections internal to the deployment and expose only the required application entry points.

## Git

- Use focused branches for implementation work.
- Make logically grouped changes and avoid unrelated modifications.
- Do not commit, push, open pull requests, merge, deploy or change branches unless authorized.
- Never commit secrets, local environment files or generated temporary artifacts.

## Verification

- Run relevant tests and static checks according to the affected components.
- Prefer targeted verification over repeated full-suite execution.
- Preserve meaningful regression and contract tests.
- Never weaken tests simply to make production code pass.
- Report changes, verification results and unresolved issues.
- Claim completion only for work actually verified.
