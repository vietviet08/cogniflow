"""add provider model settings

Revision ID: 20260322_000003
Revises: 20260322_000002
Create Date: 2026-03-22 20:10:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260322_000003"
down_revision: str | Sequence[str] | None = "20260322_000002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE provider_credentials
            ADD COLUMN chat_model TEXT,
            ADD COLUMN embedding_model TEXT;
        """,
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE provider_credentials
            DROP COLUMN IF EXISTS embedding_model,
            DROP COLUMN IF EXISTS chat_model;
        """,
    )
