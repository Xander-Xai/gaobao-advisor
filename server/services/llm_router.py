"""LLM multi-provider router with fallback chains."""

from __future__ import annotations

import logging
from enum import Enum

from config.loader import load_llm_config

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


def _get_fast_providers() -> list[str]:
    """Read fast provider list from llm_providers.yaml roles."""
    config = load_llm_config()
    return list(config.get("roles", {}).get("fast", ["agnes-flash-1", "agnes-flash-2"]))


def _get_smart_provider() -> str:
    """Read smart provider from llm_providers.yaml roles."""
    config = load_llm_config()
    smart = config.get("roles", {}).get("smart", [])
    return smart[0] if smart else "glm-4"


class LLMRouter:
    def __init__(self) -> None:
        self._agnes_index = 0

    def route(self, task_type: TaskType | str) -> str:
        task = TaskType(task_type) if isinstance(task_type, str) else task_type
        fast_providers = _get_fast_providers()
        if task in FAST_TASKS and fast_providers:
            provider = fast_providers[self._agnes_index % len(fast_providers)]
            self._agnes_index += 1
            return provider
        elif task in SMART_TASKS:
            return _get_smart_provider()
        else:
            if fast_providers:
                provider = fast_providers[self._agnes_index % len(fast_providers)]
                self._agnes_index += 1
                return provider
            return _get_smart_provider()

    def build_fallback_chain(self, primary: str) -> list[str]:
        fast_providers = _get_fast_providers()
        smart = _get_smart_provider()
        if primary in fast_providers:
            others = [p for p in fast_providers if p != primary]
            return [primary] + others + [smart]
        elif primary == smart:
            return [smart] + fast_providers
        else:
            return [primary] + fast_providers + [smart]
