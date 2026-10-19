"""Deployment/config contract tests.

Covers the P1 findings:
* a missing production SESSION_SECRET fails at startup, not on first request;
* the development secret is persisted so restarts / local workers agree;
* health exposes liveness and readiness separately from optional capabilities.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import server.auth as auth
from server.main import app


class TestSessionSecretStartup:
    def test_production_without_secret_fails_fast(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.delenv("SESSION_SECRET", raising=False)
        monkeypatch.setattr(auth, "_SECRET", None, raising=False)
        monkeypatch.chdir(tmp_path)  # no data/.session_secret here
        with pytest.raises(RuntimeError, match="SESSION_SECRET"):
            auth.ensure_secret_ready()

    def test_production_with_secret_is_ready(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("SESSION_SECRET", "a" * 64)
        monkeypatch.setattr(auth, "_SECRET", None, raising=False)
        monkeypatch.chdir(tmp_path)
        auth.ensure_secret_ready()
        assert auth.create_session_token("s1")

    def test_app_lifespan_fails_fast_in_production(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.delenv("SESSION_SECRET", raising=False)
        monkeypatch.setattr(auth, "_SECRET", None, raising=False)
        monkeypatch.chdir(tmp_path)
        with pytest.raises(RuntimeError, match="SESSION_SECRET"):
            with TestClient(app):
                pass

    def test_development_secret_is_persisted(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.delenv("SESSION_SECRET", raising=False)
        monkeypatch.setattr(auth, "_SECRET", None, raising=False)
        monkeypatch.chdir(tmp_path)
        auth.ensure_secret_ready()
        first = auth.create_session_token("s1")
        # A fresh resolution (simulating a second worker/restart) must agree.
        monkeypatch.setattr(auth, "_SECRET", None, raising=False)
        auth.ensure_secret_ready()
        assert auth.create_session_token("s1") == first
        assert (tmp_path / "data" / ".session_secret").exists()


class TestHealthProbes:
    def test_liveness_is_dependency_free(self) -> None:
        with TestClient(app) as client:
            response = client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_readiness_reports_required_and_optional(self) -> None:
        with TestClient(app) as client:
            response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["database"] == "connected"
        assert body["optional_services"]["rag"]["state"] == "RAG_ENABLED"

    def test_readiness_is_503_when_database_is_down(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("server.routes.health.is_db_connected", lambda: False)
        with TestClient(app) as client:
            response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json()["status"] == "not_ready"
