"""add provider credentials

Revision ID: 20260322_000002
Revises: 20260315_000001
Create Date: 2026-03-22 18:20:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260322_000002"
down_revision: str | Sequence[str] | None = "20260315_000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE provider_credentials (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            api_key TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE UNIQUE INDEX uq_provider_credentials_project
            ON provider_credentials(project_id, provider);
        CREATE INDEX idx_provider_credentials_project_id
            ON provider_credentials(project_id);
        """,
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS provider_credentials;
        """,
    )
