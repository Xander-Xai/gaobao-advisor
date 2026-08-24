"""Tests for session ownership across chat and profile endpoints."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from server.main import app

client = TestClient(app)


class _FakeGraph:
    def invoke(self, state):
        return {
            "session_id": state["session_id"],
            "reply": "请补充你的省份和分数。",
            "slots": {"scene": state["scene"]},
        }


class TestChatSessionOwnership:
    def test_server_can_issue_owned_session(self):
        response = client.post("/api/v1/session", json={"scene": "gaokao"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["session_id"].startswith("session-")
        assert payload["session_token"]
        assert payload["scene"] == "gaokao"

    def test_chat_without_token_returns_401(self):
        response = client.post(
            "/api/v1/chat",
            json={"session_id": "victim-session", "message": "你好", "scene": "gaokao"},
        )
        assert response.status_code == 401

    def test_token_for_other_session_cannot_take_over_chat(self):
        from server.auth import create_session_token

        attacker_token = create_session_token("attacker-session")
        response = client.post(
            "/api/v1/chat",
            json={"session_id": "victim-session", "message": "读取会话", "scene": "gaokao"},
            headers={"Authorization": f"Bearer {attacker_token}"},
        )
        assert response.status_code == 401

    def test_chat_returns_session_token_in_done_event(self, monkeypatch):
        """Authorized chat keeps returning the same ownership token in done."""
        from server.auth import create_session_token

        monkeypatch.setattr("server.routes.chat.get_advisor_graph", lambda: _FakeGraph())

        async def fake_post_generation(state):
            return state

        monkeypatch.setattr("server.routes.chat._run_post_generation", fake_post_generation)
        token = create_session_token("test-auth-001")

        response = client.post(
            "/api/v1/chat",
            json={
                "session_id": "test-auth-001",
                "message": "你好",
                "scene": "gaokao",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        events = []
        for line in response.text.split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
        done_events = [event for event in events if event.get("type") == "done"]

        assert len(done_events) == 1
        assert done_events[0]["session_token"] == token

    def test_feedback_requires_session_token(self):
        response = client.post(
            "/api/v1/chat/feedback",
            json={"session_id": "test-auth-001", "message_index": 0, "rating": "helpful"},
        )
        assert response.status_code == 401

    def test_highlight_requires_session_token(self):
        response = client.post(
            "/api/v1/chat/highlight",
            json={"session_id": "test-auth-001", "content": "这是一段足够长的测试金句内容", "score": 80},
        )
        assert response.status_code == 401


class TestProfileAuth:
    def test_profile_without_token_returns_401(self):
        response = client.get("/api/v1/profile/test-auth-001")
        assert response.status_code == 401

    def test_profile_with_valid_token_returns_200(self):
        from server.auth import create_session_token

        token = create_session_token("test-auth-001")
        response = client.get(
            "/api/v1/profile/test-auth-001",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    def test_profile_with_invalid_token_returns_401(self):
        response = client.get(
            "/api/v1/profile/test-auth-001",
            headers={"Authorization": "Bearer invalid-token-xxx"},
        )
        assert response.status_code == 401
