"""audit pagination performance index

Revision ID: 20261031_0004
Revises: 20261031_0003
Create Date: 2026-10-31

The audit list orders by ``created_at DESC, id DESC`` without an action filter.
The existing composite indexes lead with action/actor, so they cannot satisfy
the default ordering. A single-column audit index is additive. A matching
jobs index was benchmarked but not adopted because MySQL did not use it.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision = "20261031_0004"
down_revision = "20261031_0003"
branch_labels = None
depends_on = None


def _create_index_if_missing(table: str, name: str, columns: list[str]) -> None:
    existing = {index["name"] for index in inspect(op.get_bind()).get_indexes(table)}
    if name not in existing:
        op.create_index(name, table, columns)


def upgrade() -> None:
    _create_index_if_missing("operation_audit_logs", "ix_audit_created", ["created_at"])


def downgrade() -> None:
    existing_audit = {index["name"] for index in inspect(op.get_bind()).get_indexes("operation_audit_logs")}
    if "ix_audit_created" in existing_audit:
        op.drop_index("ix_audit_created", table_name="operation_audit_logs")
