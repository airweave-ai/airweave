# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Airweave?

Airweave is an open-source platform that makes any app searchable for AI agents by syncing data from 50+ sources into vector databases. It serves as a context retrieval layer for RAG systems and AI agents.

## Architecture

Monorepo with four main components:
- **Backend** (`backend/`): Python 3.13, FastAPI, SQLAlchemy async, PostgreSQL
- **Frontend** (`frontend/`): React 18, TypeScript, Vite, ShadCN UI, TailwindCSS
- **Workers**: Temporal for async sync orchestration, Redis for pub/sub
- **MCP Server** (`mcp/`): Node.js, Streamable HTTP transport for AI assistant integration

Data flow: Sources → Entity extraction → Transformation (DAG) → Embedding → Vector DB → Agent queries

## Common Commands

### Local Development (Docker)
```bash
./start.sh                     # Start all services
./start.sh --skip-frontend     # Backend only
./start.sh --restart           # Restart services
./start.sh --destroy           # Tear down everything
```

### Backend

Use **Poetry 2.3+** to match CI. `tool.poetry.requires-poetry` is omitted because Poetry 1.x rejects that key as an invalid `[tool.poetry]` field, which breaks `poetry run` (e.g. pre-commit hooks).

```bash
cd backend
poetry install                 # Install dependencies
poetry run uvicorn airweave.main:app --host 0.0.0.0 --port 8001 --reload  # Dev server

# Tests
poetry run pytest tests/unit                          # Unit tests only
poetry run pytest tests/integration                   # Integration tests
poetry run pytest tests/e2e                           # E2E tests
poetry run pytest tests/unit/test_foo.py              # Single file
poetry run pytest tests/unit/test_foo.py::test_bar    # Single test
poetry run pytest -m "not slow"                       # Skip slow tests

# Code quality
poetry run ruff check .        # Lint
poetry run ruff format .       # Format
poetry run black .             # Alt formatter (88 chars)
poetry run mypy airweave       # Type checking
lint-imports                   # Import architecture validation
```

### Frontend
```bash
cd frontend
npm install                    # Install dependencies
npm run dev                    # Dev server on :8080
npm run build                  # Production build
npm run lint                   # ESLint
```

## Backend Structure

```
backend/airweave/
├── api/v1/endpoints/    # FastAPI route handlers (one router per resource)
├── models/              # SQLAlchemy ORM models (UUID PKs)
├── schemas/             # Pydantic request/response schemas
├── crud/                # Database access (base classes: _base_organization, _base_user, _base_public)
├── domains/             # Business logic (service.py, repository.py, protocols.py per domain)
├── platform/
│   ├── sources/         # 50+ source connectors (Notion, Slack, etc.)
│   ├── destinations/    # Vector DB adapters
│   ├── embedding_models/# Embedding providers
│   ├── entities/        # Entity type definitions per source
│   └── temporal/        # Temporal worker and activities
├── core/
│   ├── config/          # Pydantic Settings (env vars)
│   ├── container/       # Dependency injection container + factory
│   ├── exceptions.py    # Custom exception hierarchy
│   └── logging.py       # structlog-based logging
├── adapters/            # External service adapters (PostHog, Stripe, etc.)
└── search/              # Search providers (Vespa)
```

Key concepts:
- `short_name` is a globally unique identifier for sources/entities (e.g., `slack`, `hubspot_crm`)
- `ApiContext` is injected into every endpoint — contains user, org, logger, cache, rate limiter
- Domain services use protocol-based DI; `Container` dataclass holds implementations, `Factory` builds it
- Alembic migrations run automatically on startup (144+ migration files in `backend/alembic/versions/`)

## Frontend Structure

```
frontend/src/
├── components/
│   ├── ui/              # ShadCN base components (40+)
│   └── [feature]/       # Feature-grouped components
├── pages/               # Route-level components
├── lib/
│   ├── api.ts           # API client (token mgmt, org context, SSE, retry)
│   ├── stores/          # Zustand stores (organizations, collections, etc.)
│   ├── auth-context.tsx # Auth0 wrapper with dev-mode fallback
│   └── validation/      # Zod-based validation rules
├── hooks/               # Custom React hooks
├── config/              # env.ts, auth.ts
└── types/index.ts       # Shared TypeScript types (mirrors backend Pydantic schemas)
```

Key patterns:
- API client: always use relative paths, no `/api/v1` prefix — e.g., `apiClient.get('/collections')`
- Auto-injected headers: `X-Organization-ID`, `X-Airweave-Session-ID` (PostHog session replay)
- Zustand for global state, React Query for server state, local state for UI-only concerns
- Component order: hooks → effects → handlers → render
- Path alias: `@/` maps to `./src`

## Code Style

### Backend (Python)
- Ruff: 100-char lines, Google docstrings, double quotes
- Async for all I/O operations
- Typed parameters and returns; functions under 50 lines
- RESTful endpoints — version is NOT part of the URL path (just `host.com/{endpoint}`)
- Use logger from `ctx` (API) or `sync_context` (during sync)
- Security: never use `random.*` for security values (ruff S311); use `secrets` module

### Frontend (TypeScript)
- TailwindCSS with `cn()` utility for class merging
- Strict typing; shared interfaces in `types/index.ts`
- Never use `Math.random()` (ESLint ban); use `crypto.getRandomValues()` or `crypto.randomUUID()`
- Toast notifications via Sonner: `toast.success()`, `toast.error()`, etc.

## Testing

### Backend test markers
- `@pytest.mark.unit` — fast, isolated
- `@pytest.mark.integration` — requires database/services
- `@pytest.mark.live_integration` — requires live cloud infrastructure
- `@pytest.mark.e2e` — end-to-end
- `@pytest.mark.slow` — long-running

Async mode is `auto` — async test functions are detected automatically.

### Monke (E2E Framework)
Located in `monke/`. Tests source connectors end-to-end by creating real test data in external systems, triggering syncs, and verifying results in the search index. Components:
- `monke/bongos/{short_name}.py` — test data creation/cleanup
- `monke/generation/schemas/{short_name}.py` — generation schemas
- `monke/configs/{short_name}.yaml` — test configuration

## OAuth Browser Flow Contract

1. `POST /source-connections` returns `auth.claim_token` → store in `sessionStorage` as `oauth_claim_token:{source_connection_id}`
2. After OAuth redirect, call `POST /source-connections/{id}/verify-oauth` with `{ claim_token }`
3. Only remove sessionStorage entry after successful `verify-oauth` response

Skipping `verify-oauth` leaves the sync stuck in `PENDING`.

## Infrastructure Notes

- Adjacent `infra-core` repository manages all infrastructure
- Docker Compose for dev; Kubernetes for prod
- PostgreSQL (metadata), Redis (pub/sub + caching), Vespa/Qdrant (vectors), Temporal (orchestration)
- Auth0 for user auth (can disable with `AUTH_ENABLED=False` for local dev)
- Pre-commit hooks enforce ruff, mypy, import-linter, ESLint
