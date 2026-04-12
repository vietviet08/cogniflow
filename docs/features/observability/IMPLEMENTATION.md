# Observability Implementation

Status: Implemented baseline
Date: 2026-04-12
Branch: `feature/observability`

## Scope Delivered

- Added structured JSON logging with request-bound context in `api/app/core/logging.py`
- Added request correlation ID middleware in `api/app/main.py`
- Propagated `x-request-id` into:
  - request context
  - response header
  - success/error envelope metadata
  - async worker job payloads
- Implemented in-memory telemetry registry in `api/app/observability/telemetry.py`
- Recorded request counts, request latency, job counts, job latency, and recent trace events
- Added public metrics snapshot endpoint: `GET /api/v1/metrics`
- Instrumented worker runtime for `job_started`, `job_completed`, and `job_failed`
- Added tests for request ID propagation, metrics snapshot, and worker metric recording

## Files Changed

- `api/app/core/logging.py`
- `api/app/observability/telemetry.py`
- `api/app/contracts/common.py`
- `api/app/main.py`
- `api/app/api/routes/health.py`
- `api/app/workers/tasks.py`
- `api/app/api/routes/processing.py`
- `api/app/api/routes/insights.py`
- `api/app/api/routes/reports.py`
- `api/tests/contract/test_health_contract.py`
- `api/tests/workers/test_worker_runtime.py`

## Notes

- Metrics are kept in process memory for now, which is enough for local dev and CI but not durable across restarts.
- The current trace surface is a lightweight event log, not a full external tracing exporter.
- Request route labels use the resolved route path where available to avoid high-cardinality metrics keys.

## Verification

- `cd api && ruff check ...`
- `cd api && pytest tests/contract tests/workers -q`
