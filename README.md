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
- Model selection is also configured per project in the frontend at `/settings`.
- There is no AI-provider fallback in `api/.env`; if a project is not configured, processing/query
  requests fail until the user adds the provider settings in UI.
- Processing and indexing currently use the OpenAI provider config plus its selected embedding model.
- Query answer generation can run with `OpenAI` or `Gemini` from the query UI, using the selected
  model for that provider.
- Gemini query mode still depends on the project OpenAI key for retrieval embeddings, because the
  current vector store is indexed with OpenAI embeddings.

Detailed commands: `docs/DEVELOPMENT_COMMANDS.md`.

## Actionable Outputs MVP

The reports workflow now supports structured, practical output templates in addition to markdown:

- `action_items`: extract concrete follow-ups, suggested owners, and due date hints
- `risk_analysis`: surface source-grounded risks with mitigation recommendations
- `executive_brief`: summarize key points, decisions needed, and next steps

Each actionable output is persisted with a `structured_payload` in the backend and rendered in the
frontend as a dedicated view, while still producing markdown for export and sharing.
