"""async_worker_runtime

Revision ID: 20260412_000010
Revises: 20260412_000009
Create Date: 2026-04-12 11:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260412_000010"
down_revision: Union[str, Sequence[str], None] = "20260412_000009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("jobs", sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("jobs", sa.Column("queue_name", sa.String(length=50), nullable=True))
    op.add_column("jobs", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
    op.add_column("jobs", sa.Column("error_code", sa.String(length=100), nullable=True))
    op.add_column("jobs", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("job_payload", sa.JSON(), nullable=True))
    op.add_column("jobs", sa.Column("result_payload", sa.JSON(), nullable=True))
    op.add_column("jobs", sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "finished_at")
    op.drop_column("jobs", "started_at")
    op.drop_column("jobs", "cancel_requested_at")
    op.drop_column("jobs", "result_payload")
    op.drop_column("jobs", "job_payload")
    op.drop_column("jobs", "error_message")
    op.drop_column("jobs", "error_code")
    op.drop_column("jobs", "idempotency_key")
    op.drop_column("jobs", "queue_name")
    op.drop_column("jobs", "max_retries")
    op.drop_column("jobs", "attempt_count")
