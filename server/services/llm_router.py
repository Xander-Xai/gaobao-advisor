"""LLM multi-provider router with fallback chains."""

from __future__ import annotations
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    FAQ = "faq"
    DATA_QUERY = "data_query"
    RAG = "rag"
    SUMMARY = "summary"
    REPORT_FORMAT = "report_format"
    RECOMMEND = "recommend"
    STRATEGY = "strategy"
    QUALITY_CHECK = "quality_check"
    STRUCTURED_OUTPUT = "structured_output"

FAST_TASKS = {TaskType.FAQ, TaskType.DATA_QUERY, TaskType.RAG, TaskType.SUMMARY, TaskType.REPORT_FORMAT}
SMART_TASKS = {TaskType.RECOMMEND, TaskType.STRATEGY, TaskType.QUALITY_CHECK, TaskType.STRUCTURED_OUTPUT}
AGNES_PROVIDERS = ["agnes-flash-1", "agnes-flash-2"]
SMART_PROVIDER = "glm-4"


class LLMRouter:
    def __init__(self) -> None:
        self._agnes_index = 0

    def route(self, task_type: TaskType | str) -> str:
        task = TaskType(task_type) if isinstance(task_type, str) else task_type
        if task in FAST_TASKS:
            provider = AGNES_PROVIDERS[self._agnes_index % len(AGNES_PROVIDERS)]
            self._agnes_index += 1
            return provider
        elif task in SMART_TASKS:
            return SMART_PROVIDER
        else:
            provider = AGNES_PROVIDERS[self._agnes_index % len(AGNES_PROVIDERS)]
            self._agnes_index += 1
            return provider

    def build_fallback_chain(self, primary: str) -> list[str]:
        if primary.startswith("agnes"):
            other = "agnes-flash-2" if primary == "agnes-flash-1" else "agnes-flash-1"
            return [primary, other, SMART_PROVIDER]
        elif primary == SMART_PROVIDER:
            return [SMART_PROVIDER, "agnes-flash-1", "agnes-flash-2"]
        else:
            return [primary, "agnes-flash-1", "agnes-flash-2", SMART_PROVIDER]
