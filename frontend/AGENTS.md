
# Frontend — Agent Guide

The root `AGENTS.md` also applies.

Frontend stack: React + Vite.

Work within `frontend/` and follow the project's existing structure and conventions.

## Sources of Truth

Consult only the documentation relevant to the task:

- Functional requirements: `docs/01-requirements/functional.md`
- Non-functional requirements: `docs/01-requirements/non-functional.md`
- API contract: `docs/03-api/openapi.yaml`
- Wireframes: `docs/04-frontend/Thesora_Wireframes_Diseno_y_Comportamientos.pdf`
- Brand identity: `docs/04-frontend/Thesora_Manual_de_Marca.pdf`

All paths are relative to the repository root.

## Implementation

- Preserve the approved wireframes, interactions and responsive behavior.
- Reuse existing components, styles and patterns before introducing new ones.
- Keep components focused and separate presentation from API communication.
- Use shared components for desktop and mobile unless their behavior genuinely differs.
- Keep navigation, loading, empty and error states consistent.
- Follow the brand guidelines for typography, colors and visual hierarchy.
- Avoid unnecessary abstractions, dependencies and unrelated redesigns.

## API Integration

- Follow `docs/03-api/openapi.yaml` for requests, responses and error handling.
- Use the project's `.env` and Vite environment variables (`VITE_*`) for public runtime configuration.
- Centralize API communication instead of scattering requests across components.
- Treat the backend as authoritative for business rules, permissions and persisted state.
- Replace mock data and simulated transitions with real API behavior when integrating the corresponding functionality.
- Do not silently modify API contracts to accommodate frontend assumptions.

## Verification

- Run the configured frontend build after changes.
- Run relevant existing tests and static checks when applicable.
- Verify responsive behavior and interaction states for affected functionality.
- Do not perform extensive browser or screenshot-based visual audits unless requested.
- Report verification results and unresolved issues without claiming unexecuted checks.
