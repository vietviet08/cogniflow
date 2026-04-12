"""auth_password_rbac

Revision ID: 20260412_000011
Revises: 20260412_000010
Create Date: 2026-04-12 12:30:00.000000
"""

from __future__ import annotations

import hashlib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260412_000011"
down_revision: Union[str, Sequence[str], None] = "20260412_000010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _default_password_hash() -> str:
    rounds = 600_000
    salt = "bootstrap-admin"
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        b"admin",
        salt.encode("utf-8"),
        rounds,
    ).hex()
    return f"pbkdf2_sha256${rounds}${salt}${digest}"


def upgrade() -> None:
    default_hash = _default_password_hash()
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), nullable=False, server_default="admin"),
    )
    op.execute(
        sa.text(
            "UPDATE users SET password_hash = :password_hash WHERE password_hash IS NULL"
        ).bindparams(password_hash=default_hash)
    )
    op.alter_column("users", "password_hash", nullable=False)


def downgrade() -> None:
    op.drop_column("users", "role")
    op.drop_column("users", "password_hash")
