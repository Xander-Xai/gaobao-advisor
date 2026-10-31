"""Public data-catalog response models.

These models define the contract used by the read-only data explorer. They are
deliberately separate from the administrator DTOs: the public surface exposes
aggregates and provenance, never internal review/audit fields.
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel, Field


class DatasetSnapshotOut(BaseModel):
    dataset_version: str
    profile: str
    source_note: str | None = None
    generated_at: datetime.datetime
    year_from: int | None = None
    year_to: int | None = None
    seed: int | None = None
    is_synthetic: bool = False


class YearCountOut(BaseModel):
    year: int
    count: int


class DataCountsOut(BaseModel):
    schools: int = 0
    majors: int = 0
    admission_scores: int = 0
    enrollment_plans: int = 0
    subject_rankings: int = 0
    score_rank_rows: int = 0


class DataOverviewOut(BaseModel):
    data_profile: str
    notice: str
    counts: DataCountsOut
    years: list[int] = Field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None
    provinces: list[str] = Field(default_factory=list)
    levels: list[str] = Field(default_factory=list)
    school_types: list[str] = Field(default_factory=list)
    subject_types: list[str] = Field(default_factory=list)
    scores_by_year: list[YearCountOut] = Field(default_factory=list)
    schools_with_scores: int = 0
    schools_with_plans: int = 0
    latest_admission_year: int | None = None
    snapshot: DatasetSnapshotOut | None = None


class FilterOptionsOut(BaseModel):
    provinces: list[str] = Field(default_factory=list)
    levels: list[str] = Field(default_factory=list)
    school_types: list[str] = Field(default_factory=list)
    years: list[int] = Field(default_factory=list)
    subject_types: list[str] = Field(default_factory=list)
    majors: list[str] = Field(default_factory=list)


class SchoolSummaryOut(BaseModel):
    id: int
    name: str
    province: str
    city: str = ""
    level: str
    school_type: str
    ranking: int | None = None
    is_985: bool = False
    is_211: bool = False
    is_double_first_class: bool = False
    special_type: str | None = None
    data_source_note: str | None = None
    score_count: int = 0
    plan_count: int = 0
    latest_year: int | None = None
    latest_min_score: int | None = None


class ScoreRowOut(BaseModel):
    id: int
    major_name: str | None = None
    province: str
    year: int
    batch: str
    subject_type: str
    min_score: int | None = None
    avg_score: float | None = None
    max_score: int | None = None
    min_rank: int | None = None
    plan_count: int | None = None


class PlanRowOut(BaseModel):
    id: int
    major_name: str | None = None
    province: str
    year: int
    plan_count: int | None = None
    subject_requirement: str | None = None
    batch: str | None = None
    duration: int | None = None
    tuition: int | None = None


class DataAvailabilityOut(BaseModel):
    has_scores: bool
    has_plans: bool
    available_years: list[int] = Field(default_factory=list)
    subject_types: list[str] = Field(default_factory=list)


class SchoolDetailOut(SchoolSummaryOut):
    website: str | None = None
    description: str | None = None
    scores: list[ScoreRowOut] = Field(default_factory=list)
    plans: list[PlanRowOut] = Field(default_factory=list)
    data_availability: DataAvailabilityOut


class TrendPointOut(BaseModel):
    year: int
    min_score: int | None = None
    avg_score: float | None = None
    max_score: int | None = None
    min_rank: int | None = None
    record_count: int = 0


class TrendSeriesOut(BaseModel):
    subject_type: str
    points: list[TrendPointOut] = Field(default_factory=list)
    direction: str = "数据不足"
    change: float | None = None


class TrendOut(BaseModel):
    school_id: int
    school_name: str
    province: str
    scope: str
    major: str | None = None
    aggregation: str
    series: list[TrendSeriesOut] = Field(default_factory=list)
    missing_years: list[int] = Field(default_factory=list)
    notice: str
