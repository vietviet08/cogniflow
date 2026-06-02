# AGENTS.md — NoteMesh (Cogniflow)

## Project Overview

Monorepo with two services:
- `api/` — FastAPI backend (Python 3.12), PostgreSQL, ChromaDB vector store
- `web/` — Next.js 15 frontend (React 19, TypeScript), static export mode

Production: AWS (ap-southeast-1), domain `catcosy.shop`

## Quick Start

```bash
# 1. Environment files
cp api/.env.example api/.env
cp web/.env.example web/.env.local

# 2. Start local infra (PostgreSQL 16 + ChromaDB)
docker compose -f infra/docker/docker-compose.local.yml up -d

# 3. Install deps
python3 -m pip install -r api/requirements-dev.txt
cd web && npm install

# 4. Apply migrations
cd api && alembic upgrade head

# 5. Run services (separate terminals)
cd api && WATCHFILES_FORCE_POLLING=true fastapi dev app/main.py --reload-dir app --reload-dir alembic
cd web && npm run dev
```

Or use PowerShell shortcut: `pwsh infra/scripts/dev.ps1`

## Developer Commands

### Backend (run from `api/`)

```bash
ruff check app tests              # Lint
mypy app                          # Typecheck
pytest tests/contract             # Contract tests (CI runs only these)
pytest tests                      # All tests
python -m scripts.check_contract_sync  # Schema/API spec sync guardrail
alembic heads                     # Must show exactly 1 head
alembic revision -m "message"     # Create migration
alembic upgrade head              # Apply migrations
python -m scripts.seed_demo       # Seed demo data
```

### Frontend (run from `web/`)

```bash
npm run lint        # ESLint
npm run typecheck   # tsc --noEmit
npm run test        # vitest run
npm run build       # Production static export (output: web/out/)
```

### Cross-service

```bash
pwsh infra/scripts/lint.ps1   # Lint both
pwsh infra/scripts/test.ps1   # Test both
```

## CI Pipeline (`.github/workflows/ci.yml`)

**Backend job** (Python 3.12):
1. `ruff check app tests`
2. `python -m scripts.check_contract_sync` — fails if ORM models or API spec drift from docs
3. `alembic heads` — must have exactly 1 head (no divergent migrations)
4. `py_compile scripts/smoke_staging.py`
5. `mypy app`
6. `pytest tests/contract`

**Frontend job** (Node 20):
1. `npm run lint`
2. `npm run typecheck`
3. `npm run test`
4. `npm run build`

## Architecture Notes

### Backend (`api/`)

- **Entrypoint**: `app/main.py` → `create_app()` factory
- **Routes**: `app/api/routes/` — 21 route modules, all mounted under `/api/v1`
- **Services**: `app/services/` — 18 business logic services
- **Storage**: `app/storage/models.py` — 28 SQLAlchemy ORM models; `app/storage/repositories/` — 14 repository modules
- **Workers**: `app/workers/tasks.py` — 4 async job handlers (processing, insight, report, intelligence)
- **Worker runtime**: `app/workers/runtime.py` — polling loop, runs inline by default (`WORKER_INLINE_EXECUTION=true`)
- **Engines**: `app/engines/` — domain logic by lifecycle stage (ingestion, processing, query, insight, report)
- **Config**: `app/core/config.py` — Pydantic Settings, loads from `.env`

### Frontend (`web/`)

- **Static export**: `output: "export"` in `next.config.ts` — no SSR, no API routes
- **State**: Zustand (`src/lib/project-store.ts`)
- **API client**: `src/lib/api/client.ts` — typed fetch wrapper, auto-attaches Bearer token
- **Path alias**: `@/*` maps to `./src/*`
- **Key libs**: @xyflow/react (mind maps), react-force-graph-3d (mesh visualization), @tanstack/react-query

### Data Pipeline

1. **Ingestion**: Upload files → parse (PyMuPDF, pdfplumber, python-docx) → store in `data/uploads/`
2. **Processing**: Chunk → Embed (sentence-transformers) → Index in ChromaDB
3. **Query**: Hybrid search (semantic + lexical) → Reciprocal Rank Fusion → LLM answer generation
4. **Insight/Report**: Evidence extraction → AI synthesis → Citation tracking

### Provider Configuration

- AI provider keys are configured **per-project in the UI** at `/settings`, NOT in `.env`
- No fallback in `api/.env` — requests fail if project not configured
- Processing uses OpenAI embeddings; query can use OpenAI or Gemini
- Gemini query still needs OpenAI key for retrieval embeddings

## Testing Quirks

- **Backend tests use SQLite in-memory** (`tests/conftest.py`) — no PostgreSQL needed for tests
- **Contract tests** (`tests/contract/`) are the CI gate — run fast, no external deps
- **Test fixture** auto-bootstraps first user and attaches auth token to `client` fixture
- **Unauthenticated tests**: use `unauthenticated_client` fixture
- **Frontend tests**: Vitest with jsdom environment, files in `web/tests/`

## Database & Migrations

- **ORM models**: `api/app/storage/models.py` — single file, 28 tables
- **Migrations**: Alembic in `api/alembic/`
- **CI guard**: must have exactly 1 Alembic head (no divergent branches)
- **Contract sync**: `scripts/check_contract_sync.py` verifies ORM + `docs/DATABASE_SCHEMA.sql` + `docs/API_SPEC.md` stay aligned

## Infrastructure

- **Docker Compose** (`infra/docker/docker-compose.local.yml`): PostgreSQL 16 (port 5432) + ChromaDB 1.0.20 (port 8001)
- **Terraform** (`infra/terraform/`): 8 modules — VPC, SG, ACM, S3, RDS, EC2, ALB, CloudFront
- **Ansible** (`infra/ansible/`): roles for common, docker, app_server, jenkins
- **EC2 bootstrap**: `infra/scripts/user_data_app.sh`, `infra/scripts/user_data_jenkins.sh`
- **Jenkins**: `Jenkinsfile` — 7 stages, deploys only on `main` branch

## Key Environment Variables

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/cogniflow` | PostgreSQL connection |
| `CHROMA_HOST` / `CHROMA_PORT` | `localhost:8001` | ChromaDB vector store |
| `WORKER_INLINE_EXECUTION` | `true` | Jobs run in-process (no separate worker needed) |
| `WORKER_POLL_INTERVAL_SECONDS` | `2` | Worker polling interval |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000/api/v1` | Frontend API base URL |

## Conventions

- **Python**: ruff line-length=100, target py312, select E/F/I/B
- **TypeScript**: strict mode, ES2022 target, bundler module resolution
- **API prefix**: all routes under `/api/v1`
- **Auth**: Bearer token in Authorization header, bootstrap first user via `POST /auth/bootstrap`
- **Roles**: viewer < editor < owner (project level); owner/admin/member (org level)
- **Job queue**: async jobs with retry (max 3), dead-letter routing
- **Error envelope**: `{"error": {"code": "...", "message": "...", "details": {...}}}`
- **Success envelope**: `{"data": {...}}`

## Common Pitfalls

- **ChromaDB must be running** before starting the API (vector operations fail silently otherwise)
- **Alembic migrations** must be applied before first run — app won't start without schema
- **`WATCHFILES_FORCE_POLLING=true`** required on Windows for FastAPI hot-reload
- **Static export**: `npm run build` produces `web/out/` — no `next start` in production
- **Provider keys**: don't put AI keys in `.env` — configure per-project in UI
- **Contract sync**: changes to ORM models or API endpoints require updating `docs/DATABASE_SCHEMA.sql` and `docs/API_SPEC.md` or CI fails
