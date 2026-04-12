# Async Worker Implementation

Status: Implemented baseline
Date: 2026-04-12
Branch: `feature/async-worker`

## Scope Delivered

- Extended `jobs` with worker runtime fields:
  - `attempt_count`
  - `max_retries`
  - `queue_name`
  - `idempotency_key`
  - `error_code`
  - `error_message`
  - `job_payload`
  - `result_payload`
  - `cancel_requested_at`
  - `started_at`
  - `finished_at`
- Added Alembic migration: `20260412_000010_async_worker_runtime.py`
- Implemented in-process worker runtime in `api/app/workers/tasks.py`
- Switched `POST /api/v1/jobs/processing` to queued execution with `BackgroundTasks`
- Added optional `mode: "async"` support to:
  - `POST /api/v1/insights/generate`
  - `POST /api/v1/reports/generate`
- Implemented real `GET /api/v1/jobs/{job_id}` progress/result surface
- Implemented real retry and cancellation state transitions for queued jobs
- Updated source processing UX to reference `job_id` instead of assuming immediate `run_id`

## Files Changed

- `api/app/storage/models.py`
- `api/app/storage/repositories/job_repository.py`
- `api/app/workers/tasks.py`
- `api/app/api/routes/processing.py`
- `api/app/api/routes/jobs.py`
- `api/app/api/routes/insights.py`
- `api/app/api/routes/reports.py`
- `api/alembic/versions/20260412_000010_async_worker_runtime.py`
- `api/tests/contract/test_processing_contract.py`
- `web/src/lib/api/types.ts`
- `web/src/components/source-manager.tsx`

## Notes

- This is an in-process async baseline, not a distributed queue.
- `processing` is now async-first.
- `insight` and `report` keep `sync` as the default mode for compatibility with the current frontend, but can already run via worker with `mode: "async"`.
- Retry and cancellation are functional baselines; dead-letter routing and automatic retry/backoff are still pending.

## Verification

- `cd api && ruff check ...` on changed worker files
- `cd api && pytest tests/contract -q`
- `cd web && npm run typecheck`
  - Blocked locally because the environment does not currently have `tsc` available in `web/node_modules/.bin`
