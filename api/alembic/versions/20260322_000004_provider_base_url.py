"""add provider base url setting

Revision ID: 20260322_000004
Revises: 20260322_000003
Create Date: 2026-03-22 22:00:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260322_000004"
down_revision: str | Sequence[str] | None = "20260322_000003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE provider_credentials
            ADD COLUMN base_url TEXT;
        """,
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE provider_credentials
            DROP COLUMN IF EXISTS base_url;
        """,
    )
