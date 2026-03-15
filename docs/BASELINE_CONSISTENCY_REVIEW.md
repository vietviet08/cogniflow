# Baseline Consistency Review

Date: 2026-03-15
Change: `bootstrap-project-source-base`

## Checked Areas

- `docs/PROJECT_STRUCTURE.md` vs scaffolded directories under `apps/`, `packages/`, `infra/`.
- `docs/API_SPEC.md` vs implemented baseline FastAPI route paths and envelope format.
- `docs/DATABASE_SCHEMA.sql` vs Alembic initial migration entities and major relationships.
- `openspec/specs/*` baseline requirements vs implemented bootstrap placeholders.

## Mismatches Found and Fixed

- Added missing API stubs for baseline endpoints:
  - `/jobs/processing`
  - `/query/search`
  - `/insights/generate`
  - `/reports/generate`
  - `/reports/{report_id}/lineage`
  - `/runs/{run_id}/replay`
  - `/jobs/{job_id}/cancel`
  - `/jobs/{job_id}/retry`
- Ensured all baseline route responses use `data/meta` or `error/meta` envelope.
- Added frontend shell routes and typed API client with env-driven base URL.

## Result

No unresolved documentation-to-bootstrap contract mismatch remains within current bootstrap scope.
