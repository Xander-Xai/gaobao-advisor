"""Auth tests for chat feedback / highlight metadata endpoints.

Regression guard for the P0 finding: ``POST /api/v1/chat/feedback`` and
``POST /api/v1/chat/highlight`` were unauthenticated, so any caller could write
rows into (or read errors from) another session's records.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from server.auth import create_session_token
from server.main import app


def _bearer(session_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_session_token(session_id)}"}


def _feedback_body(session_id: str) -> dict:
    return {"session_id": session_id, "message_index": 0, "rating": "helpful"}


def _highlight_body(session_id: str) -> dict:
    return {"session_id": session_id, "content": "这是一段足够长的合成金句内容", "score": 80}


class TestFeedbackAuth:
    def test_feedback_without_token_is_rejected(self):
        with TestClient(app) as client:
            response = client.post("/api/v1/chat/feedback", json=_feedback_body("fb-auth-owner"))
        assert response.status_code == 401

    def test_feedback_cross_session_is_rejected(self):
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/chat/feedback",
                json=_feedback_body("fb-victim-session"),
                headers=_bearer("fb-attacker-session"),
            )
        assert response.status_code == 401

    def test_feedback_with_owner_token_succeeds(self):
        session_id = "fb-auth-owner-ok"
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/chat/feedback",
                json=_feedback_body(session_id),
                headers=_bearer(session_id),
            )
        assert response.status_code == 200
        assert response.json() == {"success": True}

    def test_feedback_text_is_bounded(self):
        session_id = "fb-too-long"
        body = _feedback_body(session_id)
        body["feedback_text"] = "x" * 5000
        with TestClient(app) as client:
            response = client.post("/api/v1/chat/feedback", json=body, headers=_bearer(session_id))
        assert response.status_code == 422


class TestHighlightAuth:
    def test_highlight_without_token_is_rejected(self):
        with TestClient(app) as client:
            response = client.post("/api/v1/chat/highlight", json=_highlight_body("hl-auth-owner"))
        assert response.status_code == 401

    def test_highlight_cross_session_is_rejected(self):
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/chat/highlight",
                json=_highlight_body("hl-victim-session"),
                headers=_bearer("hl-attacker-session"),
            )
        assert response.status_code == 401

    def test_highlight_with_owner_token_succeeds(self):
        session_id = "hl-auth-owner-ok"
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/chat/highlight",
                json=_highlight_body(session_id),
                headers=_bearer(session_id),
            )
        assert response.status_code == 200
        assert response.json() == {"success": True}

    def test_highlight_oversized_content_is_bounded(self):
        session_id = "hl-too-long"
        body = _highlight_body(session_id)
        body["content"] = "长篇" * 5000
        with TestClient(app) as client:
            response = client.post("/api/v1/chat/highlight", json=body, headers=_bearer(session_id))
        assert response.status_code == 422

    def test_highlight_failure_does_not_leak_exception(self, monkeypatch):
        """A DB failure must return a generic error, never the raw exception string."""
        session_id = "hl-db-failure"

        def _boom(*_args, **_kwargs):
            raise RuntimeError("/internal/path/leaked.db is locked")

        monkeypatch.setattr("server.routes.chat.get_session", _boom)
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/chat/highlight",
                json=_highlight_body(session_id),
                headers=_bearer(session_id),
            )
        assert response.status_code == 500
        assert "leaked.db" not in response.text
        assert "/internal/path" not in response.text
