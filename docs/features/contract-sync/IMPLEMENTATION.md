# Contract Sync Implementation

Status: Implemented baseline
Date: 2026-04-12
Branch: `feature/contract-sync`

## Scope Delivered

- Updated `docs/DATABASE_SCHEMA.sql` to match implemented auth, job runtime, insight, and report models
- Updated `docs/API_SPEC.md` for:
  - auth endpoints
  - metrics endpoint
  - queued processing response
  - enriched job status payload
  - sync/async insight and report generation modes
- Updated `docs/PHASE_DEVELOPMENT_CHECKLIST.md` to reflect the new production-foundation baseline
- Added contract verification script: `api/scripts/check_contract_sync.py`
- Added contract verification tests:
  - `api/tests/contract/test_contract_sync.py`

## Files Changed

- `docs/API_SPEC.md`
- `docs/DATABASE_SCHEMA.sql`
- `docs/PHASE_DEVELOPMENT_CHECKLIST.md`
- `api/scripts/check_contract_sync.py`
- `api/tests/contract/test_contract_sync.py`

## Notes

- The contract-sync checks intentionally focus on high-risk surfaces first: auth tables, job runtime fields, insight/report shapes, and required API paths.
- The current script is suitable for local runs and CI. It is not intended to replace deeper migration verification.

## Verification

- `cd api && python -m scripts.check_contract_sync`
- `cd api && pytest tests/contract tests/workers -q`
