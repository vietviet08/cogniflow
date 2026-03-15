# Contributor Bootstrap

## Prerequisites

- Node.js 20+
- `pnpm` 10+
- Python 3.12+
- Docker

## First-Time Setup

1. Clone repository and open root.
2. Copy environment files:
   - `.env.example` -> `.env`
   - `apps/api/.env.example` -> `apps/api/.env`
   - `apps/web/.env.example` -> `apps/web/.env.local`
3. Start local dependencies:
   - `docker compose -f infra/docker/docker-compose.local.yml up -d`
4. Install dependencies:
   - `pnpm install:all`
5. Apply migrations:
   - `cd apps/api && alembic upgrade head`
6. Start applications:
   - `pnpm dev`

## Validation Checklist

- Backend health responds at `GET /api/v1/health`.
- Frontend shell is reachable and links to workflow pages.
- `pnpm lint`, `pnpm typecheck`, and `pnpm test` execute without failures.
