"""set jobs source foreign key to set null

Revision ID: 20260524_000016
Revises: 20260429_000015
Create Date: 2026-05-24 04:05:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260524_000016"
down_revision: Union[str, Sequence[str], None] = "20260429_000015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("jobs_source_id_fkey", "jobs", type_="foreignkey")
    op.create_foreign_key(
        "jobs_source_id_fkey",
        "jobs",
        "sources",
        ["source_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("jobs_source_id_fkey", "jobs", type_="foreignkey")
    op.create_foreign_key(
        "jobs_source_id_fkey",
        "jobs",
        "sources",
        ["source_id"],
        ["id"],
    )
