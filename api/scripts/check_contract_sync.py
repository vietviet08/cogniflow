from __future__ import annotations

import re
from pathlib import Path

from app.storage.models import Base

ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = ROOT / "docs"
API_SPEC_PATH = DOCS_DIR / "API_SPEC.md"
DB_SCHEMA_PATH = DOCS_DIR / "DATABASE_SCHEMA.sql"

REQUIRED_TABLE_COLUMNS = {
    "organizations": {"id", "name", "slug", "created_at"},
    "organization_memberships": {
        "id",
        "organization_id",
        "user_id",
        "role",
        "created_at",
    },
    "projects": {"id", "organization_id", "name", "description", "created_at"},
    "users": {
        "id",
        "email",
        "display_name",
        "password_hash",
        "role",
        "is_active",
        "created_at",
    },
    "auth_tokens": {
        "id",
        "user_id",
        "token_name",
        "token_hash",
        "token_last_four",
        "revoked_at",
        "created_at",
        "last_used_at",
    },
    "project_memberships": {"id", "project_id", "user_id", "role", "created_at"},
    "integration_connections": {
        "id",
        "project_id",
        "provider",
        "account_label",
        "access_token",
        "base_url",
        "connection_metadata",
        "status",
        "created_at",
        "updated_at",
    },
    "sources": {
        "id",
        "project_id",
        "type",
        "original_uri",
        "storage_path",
        "checksum",
        "source_metadata",
        "status",
        "created_at",
        "updated_at",
    },
    "jobs": {
        "id",
        "project_id",
        "source_id",
        "job_type",
        "status",
        "progress",
        "attempt_count",
        "max_retries",
        "queue_name",
        "idempotency_key",
        "error_code",
        "error_message",
        "job_payload",
        "result_payload",
        "cancel_requested_at",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
    },
    "insights": {
        "id",
        "project_id",
        "query",
        "summary",
        "findings",
        "provider",
        "model_id",
        "run_id",
        "status",
        "created_at",
    },
    "reports": {
        "id",
        "project_id",
        "query",
        "title",
        "report_type",
        "format",
        "content",
        "structured_payload",
        "status",
        "run_id",
        "created_at",
    },
    "insight_citations": {
        "id",
        "insight_id",
        "source_id",
        "source_type",
        "document_id",
        "chunk_id",
        "title",
        "url",
        "page_number",
        "created_at",
    },
    "report_insights": {
        "id",
        "report_id",
        "insight_id",
        "created_at",
    },
    "chat_sessions": {"id", "project_id", "title", "created_at", "updated_at"},
    "chat_messages": {
        "id",
        "session_id",
        "role",
        "content",
        "citations",
        "is_bookmarked",
        "rating",
        "created_at",
    },
    "radar_sources": {
        "id",
        "project_id",
        "name",
        "source_url",
        "category",
        "default_owner",
        "is_active",
        "poll_interval_minutes",
        "last_checked_at",
        "last_content_hash",
        "last_snapshot_excerpt",
        "created_at",
        "updated_at",
    },
    "radar_events": {
        "id",
        "project_id",
        "source_id",
        "event_type",
        "severity",
        "title",
        "summary",
        "event_metadata",
        "detected_at",
        "acknowledged_at",
    },
    "radar_actions": {
        "id",
        "project_id",
        "event_id",
        "parent_action_id",
        "assigned_user_id",
        "owner",
        "title",
        "description",
        "due_date_suggested",
        "priority",
        "status",
        "channel_targets",
        "completed_at",
        "created_at",
        "updated_at",
    },
    "approvals": {
        "id",
        "project_id",
        "target_type",
        "target_id",
        "status",
        "requested_by_user_id",
        "reviewed_by_user_id",
        "review_notes",
        "created_at",
        "reviewed_at",
    },
    "gtm_outputs": {
        "id",
        "project_id",
        "event_id",
        "output_type",
        "title",
        "content",
        "status",
        "created_at",
        "updated_at",
    },
    "alert_deliveries": {
        "id",
        "project_id",
        "event_id",
        "action_id",
        "provider",
        "destination",
        "status",
        "status_code",
        "response_excerpt",
        "attempt_count",
        "dispatched_at",
    },
    "public_links": {
        "id",
        "project_id",
        "target_type",
        "target_id",
        "token",
        "password_hash",
        "expires_at",
        "is_revoked",
        "created_by_user_id",
        "created_at",
        "revoked_at",
    },
    "audit_logs": {
        "id",
        "project_id",
        "organization_id",
        "user_id",
        "action",
        "target_type",
        "target_id",
        "payload",
        "created_at",
    },
}

REQUIRED_API_STRINGS = [
    "`POST /auth/bootstrap`",
    "`POST /auth/login`",
    "`GET /auth/me`",
    "`POST /auth/tokens`",
    "`GET /organizations`",
    "`GET /projects/{project_id}/members`",
    "`GET /sources/project/{project_id}`",
    "`GET /projects/{project_id}/integrations`",
    "`GET /metrics`",
    "`POST /jobs/processing`",
    "`GET /jobs/{job_id}`",
    "`POST /insights/generate`",
    "`POST /reports/generate`",
    "`POST /projects/{project_id}/chat/sessions`",
    "`GET /runs/{left_run_id}/compare/{right_run_id}`",
    "`GET /projects/{project_id}/intelligence/sources`",
    "`POST /projects/{project_id}/intelligence/scan`",
    "`POST /projects/{project_id}/intelligence/outputs`",
    "`GET /projects/{project_id}/intelligence/roi`",
    "`POST /projects/{project_id}/share-links`",
    "`POST /chat/sessions/{session_id}/messages`",
]


def load_documented_schema() -> dict[str, set[str]]:
    sql = DB_SCHEMA_PATH.read_text(encoding="utf-8")
    tables: dict[str, set[str]] = {}
    for match in re.finditer(
        r"CREATE TABLE\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\);",
        sql,
        re.DOTALL,
    ):
        table_name = match.group(1)
        body = match.group(2)
        columns: set[str] = set()
        for line in body.splitlines():
            stripped = line.strip().rstrip(",")
            if not stripped or stripped.startswith("--"):
                continue
            if stripped.upper().startswith(("CONSTRAINT", "PRIMARY KEY", "FOREIGN KEY", "UNIQUE")):
                continue
            column_name = stripped.split()[0]
            columns.add(column_name)
        tables[table_name] = columns
    return tables


def load_model_schema() -> dict[str, set[str]]:
    return {
        table_name: set(table.columns.keys())
        for table_name, table in Base.metadata.tables.items()
    }


def check_schema_contract() -> list[str]:
    documented = load_documented_schema()
    modeled = load_model_schema()
    errors: list[str] = []

    for table_name, required_columns in REQUIRED_TABLE_COLUMNS.items():
        doc_columns = documented.get(table_name)
        model_columns = modeled.get(table_name)
        if doc_columns is None:
            errors.append(f"Missing table in docs schema: {table_name}")
            continue
        if model_columns is None:
            errors.append(f"Missing table in ORM models: {table_name}")
            continue

        missing_in_docs = required_columns - doc_columns
        missing_in_models = required_columns - model_columns
        if missing_in_docs:
            errors.append(
                f"Docs schema missing columns for {table_name}: {sorted(missing_in_docs)}"
            )
        if missing_in_models:
            errors.append(
                f"ORM models missing columns for {table_name}: {sorted(missing_in_models)}"
            )

    return errors


def check_api_spec_contract() -> list[str]:
    api_spec = API_SPEC_PATH.read_text(encoding="utf-8")
    return [
        f"API spec missing required contract string: {value}"
        for value in REQUIRED_API_STRINGS
        if value not in api_spec
    ]


def main() -> int:
    errors = check_schema_contract() + check_api_spec_contract()
    if errors:
        print("Contract sync failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Contract sync passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
