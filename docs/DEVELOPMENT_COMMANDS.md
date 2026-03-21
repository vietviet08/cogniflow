# Development Commands

## Setup

- Copy environment template:
  - `cp api/.env.example api/.env`
  - `cp web/.env.example web/.env.local`
- Start local dependencies:
  - `docker compose -f infra/docker/docker-compose.local.yml up -d`
- Install backend dependencies:
  - `python3 -m pip install -r api/requirements-dev.txt`
- Install frontend dependencies:
  - `cd web && npm install`

## Run

- Start backend + frontend:
  - `pwsh infra/scripts/dev.ps1`
- Start only backend:
  - `cd api && uvicorn app.main:app --reload`
- Start only frontend:
  - `cd web && npm run dev`

## Quality Checks

- Lint:
  - `pwsh infra/scripts/lint.ps1`
- Type check:
  - `cd api && mypy app`
  - `cd web && npm run typecheck`
- Tests:
  - `pwsh infra/scripts/test.ps1`

## Database and Migrations

- Create migration:
  - `cd api && alembic revision -m "message"`
- Apply migrations:
  - `cd api && alembic upgrade head`
- Rollback one migration:
  - `cd api && alembic downgrade -1`

## Utility Scripts

- `pwsh infra/scripts/dev.ps1`
- `pwsh infra/scripts/lint.ps1`
- `pwsh infra/scripts/test.ps1`
