# Project Structure

## Service Layout

```text
note-mesh/
├── api/                             # FastAPI backend
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   └── deps/
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   └── security.py
│   │   ├── contracts/
│   │   ├── engines/
│   │   │   ├── ingestion/
│   │   │   ├── processing/
│   │   │   ├── query/
│   │   │   ├── insight/
│   │   │   └── report/
│   │   ├── services/
│   │   ├── workers/
│   │   ├── storage/
│   │   └── observability/
│   ├── alembic/
│   ├── requirements.txt
│   └── pyproject.toml
├── web/                             # Next.js frontend
│   ├── app/
│   ├── src/
│   ├── tests/
│   └── package.json
├── infra/
│   ├── docker/
│   ├── k8s/
│   ├── terraform/
│   └── scripts/
├── docs/
│   ├── AI_RESEARCH_INFRASTRUCTURE_SPEC.md
│   ├── API_SPEC.md
│   ├── DATABASE_SCHEMA.sql
│   ├── DOCS_CAPABILITY_GAP_ANALYSIS.md
│   ├── ARCHITECTURE_DIAGRAM.md
│   └── PROJECT_STRUCTURE.md
├── openspec/
│   ├── config.yaml
│   ├── specs/
│   └── changes/
└── README.md
```

## Backend Responsibility Boundaries

- `api/app/api/routes`: HTTP contract and request validation.
- `engines/*`: domain logic by lifecycle stage.
- `workers`: long-running and queue-driven execution.
- `contracts`: shared schemas for cross-engine handoffs.
- `observability`: telemetry emitters, tracing hooks, and metrics adapters.

## Documentation and Change Workflow

- `docs/` stores implementation-facing architecture and contract baseline.
- `openspec/specs/` stores accepted capability requirements.
- `openspec/changes/` stores active proposals (`proposal`, `design`, `specs`, `tasks`).

## Test Strategy Layout (Recommended)

```text
api/tests/
├── contract/        # API and schema contract tests
├── engines/         # engine-level behavior tests
├── workers/         # async job lifecycle tests
└── integration/     # end-to-end pipeline and lineage checks
```

## Ownership Guidance

- Platform team owns data contracts, job lifecycle, observability, and governance controls.
- Feature teams own endpoint handlers and user-facing workflows built on stable contracts.
