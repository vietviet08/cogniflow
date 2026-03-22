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

## Provider Keys

- API keys can now be configured per project in the frontend at `/settings`.
- Runtime uses a project-scoped provider key first, then falls back to `OPENAI_API_KEY` or
  `GEMINI_API_KEY` from `api/.env`.
- Processing and indexing currently use OpenAI embeddings.
- Query answer generation can run with `OpenAI` or `Gemini` from the query UI.
- Gemini query mode still depends on the project OpenAI key for retrieval embeddings, because the
  current vector store is indexed with OpenAI embeddings.

Detailed commands: `docs/DEVELOPMENT_COMMANDS.md`.
