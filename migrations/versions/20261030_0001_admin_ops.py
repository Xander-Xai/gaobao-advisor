"""admin operations: quality jobs, issues, audit and outbox

Revision ID: 20261030_0001
Revises:
Create Date: 2026-10-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261030_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_quality_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("review_status", sa.String(length=24), nullable=False),
        sa.Column("idempotency_key", sa.String(length=80), nullable=False),
        sa.Column("filters_json", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.String(length=64), nullable=False),
        sa.Column("execution_mode", sa.String(length=24), nullable=False),
        sa.Column("source_marker", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("checked_rows", sa.Integer(), nullable=False),
        sa.Column("issue_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("review_note", sa.String(length=500), nullable=True),
        sa.Column("reviewed_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_dq_jobs_idempotency"),
    )
    op.create_index("ix_dq_jobs_status_created", "data_quality_jobs", ["status", "created_at"])
    op.create_index("ix_dq_jobs_review", "data_quality_jobs", ["review_status", "created_at"])
    op.create_index("ix_dq_jobs_actor", "data_quality_jobs", ["requested_by", "created_at"])
    op.create_index("ix_data_quality_jobs_status", "data_quality_jobs", ["status"])
    op.create_index("ix_data_quality_jobs_review_status", "data_quality_jobs", ["review_status"])

    op.create_table(
        "data_quality_issues",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("data_quality_jobs.id"), nullable=False),
        sa.Column("rule_code", sa.String(length=40), nullable=False),
        sa.Column("severity", sa.String(length=12), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.String(length=48), nullable=False),
        sa.Column("message", sa.String(length=300), nullable=False),
        sa.Column("suggestion", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "job_id",
            "rule_code",
            "entity_type",
            "entity_id",
            "field_name",
            name="uq_quality_issue_dedup",
        ),
    )
    op.create_index("ix_data_quality_issues_job_id", "data_quality_issues", ["job_id"])
    op.create_index("ix_dq_issues_job_severity", "data_quality_issues", ["job_id", "severity"])
    op.create_index("ix_dq_issues_rule", "data_quality_issues", ["job_id", "rule_code"])

    op.create_table(
        "operation_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=40), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("detail_json", sa.Text(), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_actor_created", "operation_audit_logs", ["actor", "created_at"])
    op.create_index("ix_audit_action_created", "operation_audit_logs", ["action", "created_at"])
    op.create_index("ix_audit_request", "operation_audit_logs", ["request_id"])
    op.create_index("ix_audit_resource", "operation_audit_logs", ["resource_type", "resource_id"])

    op.create_table(
        "quality_task_outbox",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("data_quality_jobs.id"), nullable=False),
        sa.Column("topic", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("job_id", name="uq_quality_task_outbox_job_id"),
    )
    op.create_index("ix_quality_task_outbox_status", "quality_task_outbox", ["status"])
    op.create_index("ix_outbox_status_next", "quality_task_outbox", ["status", "next_attempt_at"])


def downgrade() -> None:
    op.drop_table("quality_task_outbox")
    op.drop_table("operation_audit_logs")
    op.drop_table("data_quality_issues")
    op.drop_table("data_quality_jobs")
