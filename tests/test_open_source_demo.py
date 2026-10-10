"""Release-gate tests for the no-key community demo configuration."""

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


def test_default_llm_config_uses_offline_demo(monkeypatch):
    """A clean clone must not try a remote or locally installed model by default."""
    from config.loader import load_llm_config

    for key in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)

    config = load_llm_config()

    assert config["provider"] == "demo"
    assert config["base_url"] == "demo://local"
    assert config["api_key"] == ""


def test_production_validation_requires_explicit_security_settings(monkeypatch):
    """Production must fail at startup instead of accepting development defaults."""
    from config.loader import validate_deployment_settings

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        validate_deployment_settings()


def test_demo_stream_returns_disclosed_synthetic_response_without_client(monkeypatch):
    """Demo chat is deterministic and never constructs a network LLM client."""
    from server.graph.nodes import llm_node as module

    monkeypatch.setattr(
        module,
        "_config",
        {
            "provider": "demo",
            "base_url": "demo://local",
            "api_key": "",
            "model": "gaobao-demo",
        },
    )

    def fail_if_called():
        raise AssertionError("demo mode attempted to create a network client")

    monkeypatch.setattr(module, "_get_llm_client", fail_if_called)
    chunks = list(
        module.llm_node_stream(
            {
                "session_id": "demo-session",
                "input_text": "请给我一个演示",
                "slots": {},
                "trace": [],
            }
        )
    )

    reply = "".join(text for text, _degraded in chunks)
    assert chunks
    assert all(degraded is False for _text, degraded in chunks)
    assert "演示模式" in reply
    assert "合成" in reply
    assert "官方" in reply


def test_env_example_disables_remote_optional_services():
    """The committed example is the safe, no-key path used by new contributors."""
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "APP_ENV=development" in env_example
    assert "LLM_PROVIDER=demo" in env_example
    assert "RAG_EMBEDDING_PROVIDER=keyword" in env_example
    assert "VOICE_ENABLED=false" in env_example
    assert "SILICONFLOW_API_KEY=" not in env_example


def test_monitoring_compose_rejects_default_admin_password():
    """Production monitoring must require an explicit Grafana password."""
    compose = Path("docker-compose.monitoring.yml").read_text(encoding="utf-8")

    assert "GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:?" in compose
    assert "GRAFANA_ADMIN_PASSWORD:-admin" not in compose


@pytest.mark.asyncio
async def test_health_discloses_demo_and_optional_service_state(monkeypatch):
    """Health stays green when remote optional services are intentionally off."""
    monkeypatch.setenv("LLM_PROVIDER", "demo")
    monkeypatch.setenv("ENABLE_RAG_KB", "false")
    monkeypatch.setenv("VOICE_ENABLED", "false")

    from server.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mode"] == "demo"
    assert body["optional_services"] == {
        "rag": "disabled",
        "voice": "disabled",
    }


def test_compose_initializes_demo_database_before_api_start():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "scripts/seed_demo_data.py" in compose
    assert "GAOBAO__DB_PATH: /app/data/demo.db" in compose
    assert "LLM_PROVIDER: demo" in compose
    assert 'VOICE_ENABLED: "false"' in compose


def test_missing_restricted_knowledge_corpus_degrades_to_empty_groups(tmp_path):
    from server.services.kb_retriever import load_all_groups

    assert load_all_groups(str(tmp_path / "not-distributed")) == {}


@pytest.mark.asyncio
async def test_demo_sse_discloses_synthetic_mode_for_graph_shortcuts(monkeypatch):
    """Graph-generated shortcut replies must not bypass the demo disclosure."""
    from server.routes import chat as chat_routes

    monkeypatch.setenv("LLM_PROVIDER", "demo")
    fake_graph = type(
        "FakeGraph",
        (),
        {
            "invoke": staticmethod(
                lambda *_args, **_kwargs: {
                    "reply": "请问您来自哪个省份？",
                    "slots": {},
                    "trace": [],
                }
            )
        },
    )()
    monkeypatch.setattr(chat_routes, "get_advisor_graph", lambda: fake_graph)

    events = [
        event
        async for event in chat_routes._sse_generator(
            "demo-shortcut",
            "gaokao",
            "请给我一个演示",
            {},
        )
    ]
    token_text = "".join(
        json.loads(event.removeprefix("data: "))["content"] for event in events if '"type": "token"' in event
    )

    assert "演示模式" in token_text
    assert "合成" in token_text
    assert "非官方" in token_text
