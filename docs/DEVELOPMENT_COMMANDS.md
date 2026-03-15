# Development Commands

## Setup

- Copy environment template:
  - `cp .env.example .env`
  - `cp apps/api/.env.example apps/api/.env`
  - `cp apps/web/.env.example apps/web/.env.local`
- Start local dependencies:
  - `docker compose -f infra/docker/docker-compose.local.yml up -d`
- Install all dependencies:
  - `pnpm install:all`

## Run

- Start backend + frontend:
  - `pnpm dev`
- Start only backend:
  - `pnpm dev:api`
- Start only frontend:
  - `pnpm dev:web`

## Quality Checks

- Lint:
  - `pnpm lint`
- Type check:
  - `pnpm typecheck`
- Tests:
  - `pnpm test`

## Database and Migrations

- Create migration:
  - `cd apps/api && alembic revision -m "message"`
- Apply migrations:
  - `cd apps/api && alembic upgrade head`
- Rollback one migration:
  - `cd apps/api && alembic downgrade -1`

## Utility Scripts

- `pwsh infra/scripts/dev.ps1`
- `pwsh infra/scripts/lint.ps1`
- `pwsh infra/scripts/test.ps1`
