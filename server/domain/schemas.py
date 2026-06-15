"""Domain schemas for the advisor pipeline."""

from pydantic import BaseModel, Field


class StructuredPlanningCard(BaseModel):
    """Structured output card for planning recommendations.

    This is the JSON payload that gets sent alongside the text reply,
    enabling rich frontend rendering with facts/suggestions/risks/actions.
    """

    title: str
    summary: str
    scene: str = ""
    facts: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    confidence: float = 0.0
