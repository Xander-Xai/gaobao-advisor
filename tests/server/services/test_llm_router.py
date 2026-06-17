import pytest
from server.services.llm_router import LLMRouter, TaskType


def test_router_fast_tasks_go_to_agnes():
    router = LLMRouter()
    provider = router.route(TaskType.FAQ)
    assert provider.startswith("agnes")


def test_router_smart_tasks_go_to_glm():
    router = LLMRouter()
    provider = router.route(TaskType.RECOMMEND)
    assert provider == "glm-4"


def test_router_round_robin_agnes():
    router = LLMRouter()
    p1 = router.route(TaskType.FAQ)
    p2 = router.route(TaskType.FAQ)
    assert p1 != p2
    p3 = router.route(TaskType.FAQ)
    assert p3 == p1


def test_fallback_chain_building():
    router = LLMRouter()
    chain = router.build_fallback_chain("agnes-flash-1")
    assert chain == ["agnes-flash-1", "agnes-flash-2", "glm-4"]
    chain = router.build_fallback_chain("glm-4")
    assert chain == ["glm-4", "agnes-flash-1", "agnes-flash-2"]
