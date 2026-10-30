"""Pydantic request/response contracts for the operations workbench."""

from __future__ import annotations

import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

JobStatus = Literal["PENDING", "RUNNING", "SUCCEEDED", "FAILED"]
ReviewStatus = Literal["PENDING_REVIEW", "APPROVED", "REJECTED"]
Severity = Literal["ERROR", "WARNING", "INFO"]
SortField = Literal["id", "name", "province", "level", "ranking", "score_count"]
SortOrder = Literal["asc", "desc"]


class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=256)

    @field_validator("username")
    @classmethod
    def _strip_username(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("username is required")
        return value


class AdminUserOut(BaseModel):
    username: str
    role: Literal["viewer", "operator", "admin"]


class AdminTokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: AdminUserOut


class QualityJobFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    province: str | None = Field(default=None, max_length=20)
    level: str | None = Field(default=None, max_length=20)
    school_id: int | None = Field(default=None, ge=1)
    year: int | None = Field(default=None, ge=2000, le=2100)
    subject_type: str | None = Field(default=None, max_length=10)

    @field_validator("province", "level", "subject_type")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class QualityJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filters: QualityJobFilters = Field(default_factory=QualityJobFilters)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["APPROVED", "REJECTED"]
    note: str = Field(default="", max_length=500)
    expected_version: int = Field(ge=0)


class SchoolListItem(BaseModel):
    id: int
    name: str
    province: str
    city: str
    level: str
    school_type: str
    ranking: int | None
    is_985: int
    is_211: int
    is_double_first_class: int
    special_type: str | None
    data_source_note: str | None
    score_count: int
    plan_count: int
    latest_year: int | None
    latest_min_score: int | None


class AdmissionScoreOut(BaseModel):
    id: int
    major_name: str | None
    province: str
    year: int
    batch: str
    subject_type: str
    min_score: int | None
    avg_score: float | None
    max_score: int | None
    min_rank: int | None
    plan_count: int | None


class EnrollmentPlanOut(BaseModel):
    id: int
    major_name: str | None
    province: str
    year: int
    plan_count: int | None
    subject_requirement: str | None
    batch: str | None
    tuition: int | None


class SchoolDetailOut(SchoolListItem):
    website: str | None
    description: str | None
    scores: list[AdmissionScoreOut]
    plans: list[EnrollmentPlanOut]


class SchoolPageOut(BaseModel):
    items: list[SchoolListItem]
    total: int
    page: int
    page_size: int
    pages: int


class QualityIssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_code: str
    severity: Severity
    entity_type: str
    entity_id: int
    field_name: str
    message: str
    suggestion: str | None


class QualityJobOut(BaseModel):
    id: int
    job_type: str
    status: JobStatus
    review_status: ReviewStatus
    idempotency_key: str
    filters: dict[str, Any]
    requested_by: str
    execution_mode: str
    source_marker: str
    attempts: int
    max_attempts: int
    version: int
    checked_rows: int
    issue_count: int
    error_code: str | None
    error_message: str | None
    review_note: str | None
    reviewed_by: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    started_at: datetime.datetime | None
    finished_at: datetime.datetime | None
    reviewed_at: datetime.datetime | None


class QualityJobCreateOut(BaseModel):
    job: QualityJobOut
    replayed: bool = False
    queue_state: Literal["DISPATCHED", "INLINE", "UNAVAILABLE", "DISABLED"]
    warning: str | None = None


class QualityJobDetailOut(BaseModel):
    job: QualityJobOut
    issues: list[QualityIssueOut]


class QualityJobPageOut(BaseModel):
    items: list[QualityJobOut]
    total: int
    page: int
    page_size: int
    pages: int


class AuditLogOut(BaseModel):
    id: int
    request_id: str
    actor: str
    role: str
    action: str
    resource_type: str
    resource_id: str
    outcome: str
    detail: dict[str, Any]
    created_at: datetime.datetime


class AuditPageOut(BaseModel):
    items: list[AuditLogOut]
    total: int
    page: int
    page_size: int
    pages: int


class StatsOut(BaseModel):
    data_profile: str
    schools: int
    majors: int
    admission_scores: int
    enrollment_plans: int
    jobs_total: int
    jobs_by_status: dict[str, int]
    issues_by_severity: dict[str, int]
    schools_by_level: dict[str, int]
    pending_review: int
    audit_events: int
    last_job_at: datetime.datetime | None


class SystemStatusOut(BaseModel):
    admin_enabled: bool
    config_source: str
    database_dialect: str
    task_mode: str
    queue_state: Literal["READY", "UNAVAILABLE", "DISABLED"]
    worker_hint: str
