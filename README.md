# Cogniflow

Research assistant scaffold organized as two top-level services:

- `api/`: FastAPI backend for ingestion, processing, retrieval, and insight orchestration
- `web/`: Next.js frontend for chat, upload, and document workflows

## Tech Stack

- Ingestion: `requests`, `beautifulsoup4`, `arxiv`, `PyMuPDF`, `pdfplumber`
- RAG and generation: OpenAI `text-embedding-3-small`, `gpt-4o`, `gpt-4o-mini`
- Vector store: `ChromaDB`
- Metadata and jobs: PostgreSQL
- Frontend: Next.js 15 + React 19
- Local infra: Docker Compose for `postgres` and `chroma`

## Quick Start

1. Copy environment templates:
   - `cp api/.env.example api/.env`
   - `cp web/.env.example web/.env.local`
2. Start local dependencies:
   - `docker compose -f infra/docker/docker-compose.local.yml up -d`
3. Install backend dependencies:
   - `python3 -m pip install -r api/requirements-dev.txt`
4. Install frontend dependencies:
   - `cd web && npm install`
5. Apply backend migrations:
   - `cd api && alembic upgrade head`
6. Run the backend:
   - `cd api && uvicorn app.main:app --reload`
7. Run the frontend:
   - `cd web && npm run dev`

Detailed commands: `docs/DEVELOPMENT_COMMANDS.md`.
