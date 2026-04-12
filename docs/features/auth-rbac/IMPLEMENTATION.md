# Auth/RBAC Implementation

Status: Implemented baseline
Date: 2026-04-12
Branch: `feature/auth-rbac`

## Scope Delivered

- Added persisted auth entities: `users`, `auth_tokens`, `project_memberships`
- Added Alembic migration: `20260412_000009_auth_rbac_baseline.py`
- Added bootstrap and self-service auth endpoints:
  - `POST /api/v1/auth/bootstrap`
  - `GET /api/v1/auth/me`
  - `POST /api/v1/auth/tokens`
- Enforced bearer-token auth on non-health routes through `require_current_user`
- Enforced project-level role checks through `require_project_role`
- Auto-created owner membership when a project is created
- Restricted project listing to projects visible to the authenticated user
- Updated contract tests to authenticate through bootstrap and verify auth behavior

## Files Changed

- `api/app/core/security.py`
- `api/app/services/auth_service.py`
- `api/app/api/routes/auth.py`
- `api/app/api/routes/projects.py`
- `api/app/api/routes/sources.py`
- `api/app/api/routes/provider_settings.py`
- `api/app/api/routes/integrations.py`
- `api/app/api/routes/processing.py`
- `api/app/api/routes/query.py`
- `api/app/api/routes/insights.py`
- `api/app/api/routes/reports.py`
- `api/app/api/routes/jobs.py`
- `api/app/api/routes/runs.py`
- `api/app/api/routes/chat.py`
- `api/app/storage/models.py`
- `api/app/storage/repositories/project_repository.py`
- `api/app/storage/repositories/user_repository.py`
- `api/app/storage/repositories/auth_token_repository.py`
- `api/app/storage/repositories/project_membership_repository.py`
- `api/alembic/versions/20260412_000009_auth_rbac_baseline.py`
- `api/tests/conftest.py`
- `api/tests/contract/test_auth_contract.py`

## Notes

- This is a production-baseline token auth layer, not a full external identity solution.
- Bootstrap is intentionally limited to the first user in an empty system.
- Project authorization is currently role-threshold based: `viewer < editor < owner`.

## Verification

- `cd api && ruff check ...` on changed auth files
- `cd api && pytest tests/contract -q`
