"""add_saved_searches

Revision ID: 20260429_000015
Revises: 20260413_000014
Create Date: 2026-04-29 10:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260429_000015"
down_revision: Union[str, Sequence[str], None] = "20260413_000014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saved_searches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("report_type", sa.String(length=50), nullable=False, server_default="research_brief"),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="openai"),
        sa.Column("schedule_interval_minutes", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_saved_searches_project_id", "saved_searches", ["project_id"])
    op.create_index("idx_saved_searches_active", "saved_searches", ["is_active"])


def downgrade() -> None:
    op.drop_index("idx_saved_searches_active", table_name="saved_searches")
    op.drop_index("idx_saved_searches_project_id", table_name="saved_searches")
    op.drop_table("saved_searches")
