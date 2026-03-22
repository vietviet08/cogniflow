"""add_pdf_citation_metadata

Revision ID: 20260322_000007
Revises: 20260322_000006
Create Date: 2026-03-22 22:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260322_000007"
down_revision: Union[str, Sequence[str], None] = "20260322_000006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("insight_citations", sa.Column("source_type", sa.String(length=50), nullable=True))
    op.add_column("insight_citations", sa.Column("page_number", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("insight_citations", "page_number")
    op.drop_column("insight_citations", "source_type")
