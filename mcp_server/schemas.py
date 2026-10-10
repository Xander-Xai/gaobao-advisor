"""Pydantic schemas for MCP tool inputs and outputs."""

from pydantic import BaseModel, Field, field_validator

# ── School Schemas ──────────────────────────────────────────


class SearchSchoolsInput(BaseModel):
    """Input for searching schools."""

    school_name: str | None = Field(None, description="学校名称关键词，支持模糊匹配")
    province: str | None = Field(None, description="所在省份，如：北京、江苏")
    level: str | None = Field(None, description="学校层次，如：985、211、双一流")
    limit: int = Field(20, ge=1, le=200, description="返回结果数量上限")


class SchoolItem(BaseModel):
    """A school result item."""

    id: int
    name: str
    province: str | None = None
    level: str | None = None
    type: str | None = None
    address: str | None = None
    website: str | None = None


class SearchSchoolsOutput(BaseModel):
    """Output for school search."""

    count: int = Field(description="结果数量")
    items: list[SchoolItem] = Field(description="院校列表")
    next_cursor: str | None = Field(None, description="下一页游标")
    has_more: bool = Field(False, description="是否有更多结果")


class GetSchoolDetailInput(BaseModel):
    """Input for getting school detail."""

    school_name: str = Field(..., description="学校完整名称")


class SchoolDetail(BaseModel):
    """Detailed school information."""

    name: str
    province: str | None = None
    level: str | None = None
    type: str | None = None
    address: str | None = None
    website: str | None = None
    description: str | None = None
    majors: list[str] | None = None


# ── Score Schemas ─────────────────────────────────────────


class QueryScoresInput(BaseModel):
    """Input for querying admission scores."""

    school_name: str = Field(..., description="学校名称")
    province: str = Field(..., description="考生所在省份")
    year: int | None = Field(None, description="年份，如 2024")
    major: str | None = Field(None, description="专业名称")
    limit: int = Field(10, ge=1, le=100, description="返回记录数上限")


class ScoreRecord(BaseModel):
    """A single admission score record."""

    school_name: str
    province: str
    year: int
    batch: str | None = None
    subject_type: str | None = None
    min_score: int | None = None
    avg_score: int | None = None
    max_score: int | None = None
    min_rank: int | None = None
    major: str | None = None


class QueryScoresOutput(BaseModel):
    """Output for score query."""

    count: int
    items: list[ScoreRecord]
    has_more: bool = False


# ── Plan Schemas ──────────────────────────────────────────


class QueryPlansInput(BaseModel):
    """Input for querying enrollment plans."""

    school_name: str = Field(..., description="学校名称")
    province: str | None = Field(None, description="招生省份")
    year: int | None = Field(None, description="年份")
    limit: int = Field(10, ge=1, le=100)


class PlanRecord(BaseModel):
    """A single enrollment plan record."""

    school_name: str
    province: str
    year: int
    plan_count: int | None = None
    subject_requirement: str | None = None
    batch: str | None = None
    duration: str | None = None
    tuition: str | None = None
    major: str | None = None


class QueryPlansOutput(BaseModel):
    """Output for plan query."""

    count: int
    items: list[PlanRecord]
    has_more: bool = False


# ── Knowledge Schemas ─────────────────────────────────────


class SearchKnowledgeInput(BaseModel):
    """Input for knowledge base search."""

    query: str = Field(..., min_length=1, description="检索查询语句")
    groups: list[str] | None = Field(None, description="限定知识分组，如 ['院校', '专业']")
    top_k: int = Field(5, ge=1, le=20, description="返回结果数量")


class KnowledgeChunk(BaseModel):
    """A knowledge chunk from RAG search."""

    content: str
    group: str | None = None
    source: str | None = None
    score: float | None = None


class SearchKnowledgeOutput(BaseModel):
    """Output for knowledge search."""

    count: int
    groups: list[str]
    chunks: list[KnowledgeChunk]
    quotes: list[dict]


class GetQuotesInput(BaseModel):
    """Input for getting expert quotes."""

    major: str | None = Field(None, description="专业名称，用于过滤相关金句")
    top_k: int = Field(5, ge=1, le=20)


class QuoteItem(BaseModel):
    """An expert quote."""

    content: str
    author: str | None = None
    source: str | None = None
    tags: list[str] | None = None


class GetQuotesOutput(BaseModel):
    """Output for quotes query."""

    count: int
    quotes: list[QuoteItem]


# ── Profile Schemas ───────────────────────────────────────


class GetProfileInput(BaseModel):
    """Input for getting user profile."""

    session_id: str = Field(..., min_length=4, max_length=64, description="会话ID")


class ProfileOutput(BaseModel):
    """User profile output."""

    session_id: str
    profile: dict
    is_complete: bool
    missing_fields: list[str]


class UpdateProfileInput(BaseModel):
    """Input for updating profile field."""

    session_id: str = Field(..., min_length=4, max_length=64)
    field: str = Field(..., description="字段名：province, score, subject, interest, region, family, goal")
    value: str = Field(..., description="字段值")

    @field_validator("field")
    @classmethod
    def validate_field(cls, v: str) -> str:
        valid = {"province", "score", "subject", "interest", "region", "family", "goal"}
        if v not in valid:
            raise ValueError(f"Invalid field. Must be one of: {', '.join(sorted(valid))}")
        return v


# ── Chat Schemas ──────────────────────────────────────────


class ChatInput(BaseModel):
    """Input for chat with AI advisor."""

    session_id: str = Field(..., min_length=4, max_length=64)
    message: str = Field(..., min_length=1, max_length=3000, description="用户消息")
    scene: str = Field("gaokao", description="场景：gaokao（高考）/ postgraduate（考研）/ career（职业）")
    slots: dict | None = Field(None, description="已收集的 slot 数据")


class ChatOutput(BaseModel):
    """Chat response output."""

    session_id: str
    reply: str
    slots: dict | None = None
    emotion_state: str | None = None
    quality_grade: str | None = None


# ── System Schemas ────────────────────────────────────────


class HealthCheckOutput(BaseModel):
    """Health check response."""

    status: str
    version: str
    database: str
