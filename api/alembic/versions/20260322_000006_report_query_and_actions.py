"""add_report_query_and_action_item_updates

Revision ID: 20260322_000006
Revises: 20260322_000005
Create Date: 2026-03-22 21:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260322_000006"
down_revision: Union[str, Sequence[str], None] = "20260322_000005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("query", sa.Text(), nullable=True))
    op.execute("UPDATE reports SET query = title WHERE query IS NULL")
    op.alter_column("reports", "query", existing_type=sa.Text(), nullable=False)


def downgrade() -> None:
    op.drop_column("reports", "query")
