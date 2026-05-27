"""add quiz attempts

Revision ID: 20260527_000017
Revises: 20260524_000016
Create Date: 2026-05-27 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260527_000017"
down_revision: Union[str, Sequence[str], None] = "20260524_000016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("score_correct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_quiz_attempts_report_id", "quiz_attempts", ["report_id"])
    op.create_index("idx_quiz_attempts_user_id", "quiz_attempts", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_quiz_attempts_user_id", table_name="quiz_attempts")
    op.drop_index("idx_quiz_attempts_report_id", table_name="quiz_attempts")
    op.drop_table("quiz_attempts")
