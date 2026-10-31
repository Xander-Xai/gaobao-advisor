"""persistent administrator token revocation

Revision ID: 20261031_0003
Revises: 20261031_0002
Create Date: 2026-10-31

The revocation record is stored in the database, not only in Redis, so a Redis
restart or data loss cannot make a revoked token valid again. Downgrade is
refused because dropping the table would silently un-revoke live tokens.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from db.schema_contract import verify_table

revision = "20261031_0003"
down_revision = "20261031_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "admin_token_revocations" in inspect(bind).get_table_names():
        problems = verify_table(bind, "admin_token_revocations")
        if problems:
            raise RuntimeError("admin_token_revocations schema mismatch: " + "; ".join(problems))
        return
    op.create_table(
        "admin_token_revocations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("jti_hash", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_admin_token_revocations_jti_hash",
        "admin_token_revocations",
        ["jti_hash"],
        unique=True,
    )
    op.create_index("ix_admin_token_revocations_username", "admin_token_revocations", ["username"])
    op.create_index("ix_admin_token_revocations_expires_at", "admin_token_revocations", ["expires_at"])


def downgrade() -> None:
    raise RuntimeError(
        "20261031_0003 stores security revocation state; refusing destructive downgrade. "
        "Restore from a verified backup instead."
    )
