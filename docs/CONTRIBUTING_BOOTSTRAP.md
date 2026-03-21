# Contributor Bootstrap

## Prerequisites

- Node.js 20+
- `npm` 10+
- Python 3.12+
- Docker

## First-Time Setup

1. Clone repository and open root.
2. Copy environment files:
   - `api/.env.example` -> `api/.env`
   - `web/.env.example` -> `web/.env.local`
3. Start local dependencies:
   - `docker compose -f infra/docker/docker-compose.local.yml up -d`
4. Install dependencies:
   - `python3 -m pip install -r api/requirements-dev.txt`
   - `cd web && npm install`
5. Apply migrations:
   - `cd api && alembic upgrade head`
6. Start applications:
   - `pwsh infra/scripts/dev.ps1`

## Validation Checklist

- Backend health responds at `GET /api/v1/health`.
- Frontend shell is reachable and links to workflow pages.
- `pwsh infra/scripts/lint.ps1`, backend `mypy`, frontend `npm run typecheck`, and `pwsh infra/scripts/test.ps1` execute without failures.
