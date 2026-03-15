# NoteMesh Source Base

Bootstrap monorepo for AI research infrastructure.

## Quick Start

1. Copy `.env.example` to `.env` and adjust values.
2. Start local dependencies:
   - `docker compose -f infra/docker/docker-compose.local.yml up -d`
3. Install dependencies:
   - `pnpm install:all`
4. Run apps:
   - `pnpm dev`

Detailed commands: `docs/DEVELOPMENT_COMMANDS.md`.
