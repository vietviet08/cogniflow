"""add_structured_payload_to_reports

Revision ID: 20260322_000005
Revises: 012f8245eb94
Create Date: 2026-03-22 21:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260322_000005"
down_revision: Union[str, Sequence[str], None] = "012f8245eb94"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("structured_payload", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("reports", "structured_payload")
