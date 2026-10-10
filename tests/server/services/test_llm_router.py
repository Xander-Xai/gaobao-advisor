from server.services import llm_router as router_module
from server.services.llm_router import LLMRouter, TaskType


def test_router_fast_tasks_use_configured_fast_providers(monkeypatch):
    monkeypatch.setattr(router_module, "_get_fast_providers", lambda: ["alpha", "beta"])
    monkeypatch.setattr(router_module, "_get_smart_provider", lambda: "gamma")

    router = LLMRouter()
    provider = router.route(TaskType.FAQ)
    assert provider == "alpha"


def test_router_smart_tasks_use_configured_smart_provider(monkeypatch):
    monkeypatch.setattr(router_module, "_get_fast_providers", lambda: ["alpha", "beta"])
    monkeypatch.setattr(router_module, "_get_smart_provider", lambda: "gamma")

    router = LLMRouter()
    provider = router.route(TaskType.RECOMMEND)
    assert provider == "gamma"


def test_router_round_robin_over_fast_providers(monkeypatch):
    monkeypatch.setattr(router_module, "_get_fast_providers", lambda: ["alpha", "beta"])
    monkeypatch.setattr(router_module, "_get_smart_provider", lambda: "gamma")

    router = LLMRouter()
    p1 = router.route(TaskType.FAQ)
    p2 = router.route(TaskType.FAQ)
    p3 = router.route(TaskType.FAQ)

    assert p1 == "alpha"
    assert p2 == "beta"
    assert p3 == "alpha"


def test_fallback_chain_building(monkeypatch):
    monkeypatch.setattr(router_module, "_get_fast_providers", lambda: ["alpha", "beta"])
    monkeypatch.setattr(router_module, "_get_smart_provider", lambda: "gamma")

    router = LLMRouter()
    chain = router.build_fallback_chain("alpha")
    assert chain == ["alpha", "beta", "gamma"]

    chain = router.build_fallback_chain("gamma")
    assert chain == ["gamma", "alpha", "beta"]
