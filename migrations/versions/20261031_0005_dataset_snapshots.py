"""dataset snapshot provenance metadata

Revision ID: 20261031_0005
Revises: 20261031_0004
Create Date: 2026-10-31

The public data explorer reports when the demo dataset was generated and which
provenance profile it belongs to. Keeping that metadata in the database avoids
inferring a timestamp from row contents or the SQLite file mtime (which is not
available on MySQL). Existing custom datasets simply have no snapshot row and
are shown as "unregistered" rather than being labelled synthetic.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20261031_0005"
down_revision = "20261031_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "dataset_snapshots" in set(inspect(op.get_bind()).get_table_names()):
        return
    op.create_table(
        "dataset_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("dataset_version", sa.String(length=20), nullable=False),
        sa.Column("profile", sa.String(length=20), nullable=False),
        sa.Column("source_note", sa.String(length=200), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("year_from", sa.Integer(), nullable=True),
        sa.Column("year_to", sa.Integer(), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("is_synthetic", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    if "dataset_snapshots" in set(inspect(op.get_bind()).get_table_names()):
        op.drop_table("dataset_snapshots")
