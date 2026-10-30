"""Administrator authentication, role enforcement and fail-closed config."""

from __future__ import annotations

import json

import pytest

from server.admin.auth import (
    AdminConfigError,
    ensure_admin_ready,
    get_admin_config,
    hash_password,
    issue_admin_token,
    verify_admin_token,
)
from server.auth import create_session_token
from tests.conftest import ADMIN_PASSWORD, auth_header, login


class TestLogin:
    def test_login_returns_token_and_user(self, admin_client):
        response = admin_client.post(
            "/api/v1/admin/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["expires_in"] > 0
        assert body["user"] == {"username": "admin", "role": "admin"}
        assert body["access_token"].count(".") == 2

    def test_bad_password_returns_401_code(self, admin_client):
        response = admin_client.post(
            "/api/v1/admin/auth/login",
            json={"username": "admin", "password": "wrong-password-123"},
        )
        assert response.status_code == 401
        body = response.json()
        assert body["code"] == "INVALID_CREDENTIALS"
        assert body["message"] == "用户名或密码错误"
        assert "request_id" in body

    def test_validation_error_uses_admin_envelope(self, admin_client):
        response = admin_client.post("/api/v1/admin/auth/login", json={"username": "x", "password": "short"})
        assert response.status_code == 422
        body = response.json()
        assert body["code"] == "VALIDATION_ERROR"
        assert body["details"]["errors"]

    def test_login_is_rate_limited(self, admin_client):
        for _ in range(8):
            response = admin_client.post(
                "/api/v1/admin/auth/login",
                json={"username": "admin", "password": "wrong-password-123"},
            )
            assert response.status_code == 401
        blocked = admin_client.post(
            "/api/v1/admin/auth/login",
            json={"username": "admin", "password": "wrong-password-123"},
        )
        assert blocked.status_code == 429
        assert blocked.json()["code"] == "LOGIN_RATE_LIMITED"

    def test_me_requires_valid_admin_token(self, admin_client):
        missing = admin_client.get("/api/v1/admin/auth/me")
        assert missing.status_code == 401
        assert missing.json()["code"] == "ADMIN_TOKEN_INVALID"

        token = login(admin_client, "viewer")
        response = admin_client.get("/api/v1/admin/auth/me", headers=auth_header(token))
        assert response.status_code == 200
        assert response.json() == {"username": "viewer", "role": "viewer"}

    def test_chat_session_token_is_not_an_admin_token(self, admin_client):
        chat_token = create_session_token("anonymous-session")
        response = admin_client.get("/api/v1/admin/auth/me", headers=auth_header(chat_token))
        assert response.status_code == 401

    def test_session_scoped_endpoint_still_rejects_admin_token(self, admin_client):
        admin_token = login(admin_client, "admin")
        response = admin_client.get(
            "/api/v1/profile/unknown-session",
            headers=auth_header(admin_token),
        )
        assert response.status_code == 401


class TestRoleEnforcement:
    def test_viewer_cannot_create_quality_job(self, admin_client):
        token = login(admin_client, "viewer")
        response = admin_client.post(
            "/api/v1/admin/quality/jobs",
            json={"filters": {}},
            headers={**auth_header(token), "Idempotency-Key": "viewer-job-key-001"},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN"

    def test_viewer_cannot_read_audit_logs(self, admin_client):
        token = login(admin_client, "viewer")
        response = admin_client.get("/api/v1/admin/audit-logs", headers=auth_header(token))
        assert response.status_code == 403

    def test_operator_cannot_review(self, admin_client):
        token = login(admin_client, "operator")
        response = admin_client.post(
            "/api/v1/admin/quality/jobs/1/review",
            json={"decision": "APPROVED", "note": "", "expected_version": 0},
            headers=auth_header(token),
        )
        assert response.status_code == 403

    def test_admin_can_read_audit_logs(self, admin_client):
        token = login(admin_client, "admin")
        response = admin_client.get("/api/v1/admin/audit-logs", headers=auth_header(token))
        assert response.status_code == 200
        assert "items" in response.json()


class TestTokenSecurity:
    def test_expired_token_rejected(self, admin_client, admin_env):
        token = login(admin_client, "admin")
        config = get_admin_config()
        assert verify_admin_token(token, now=0) is not None
        assert verify_admin_token(token, now=10**11) is None
        assert config.token_ttl_seconds == 28800

    def test_tampered_payload_rejected(self, admin_client):
        token = login(admin_client, "admin")
        prefix, body, signature = token.split(".")
        tampered = f"{prefix}.{body[:-2]}AA.{signature}"
        assert verify_admin_token(tampered) is None

    def test_issue_token_without_configuration(self, monkeypatch):
        monkeypatch.setenv("ADMIN_ENABLED", "false")
        from server.admin.auth import AdminPrincipal

        with pytest.raises(AdminConfigError):
            issue_admin_token(AdminPrincipal(username="admin", role="admin"))

    def test_password_hash_roundtrip(self):
        encoded = hash_password("another-password", iterations=10_000)
        assert verify_admin_token is not None
        from server.admin.auth import verify_password

        assert verify_password("another-password", encoded)
        assert not verify_password("wrong-password", encoded)
        assert not verify_password("another-password", "not-a-hash")


class TestFailClosedConfiguration:
    def test_production_requires_separate_token_secret(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv(
            "ADMIN_USERS_JSON",
            json.dumps(
                [
                    {
                        "username": "admin",
                        "password_hash": hash_password("production-pass", iterations=10_000),
                        "role": "admin",
                    }
                ]
            ),
        )
        monkeypatch.delenv("ADMIN_TOKEN_SECRET", raising=False)
        monkeypatch.delenv("ADMIN_ENABLED", raising=False)
        with pytest.raises(AdminConfigError, match="ADMIN_TOKEN_SECRET"):
            get_admin_config()
        with pytest.raises(AdminConfigError):
            ensure_admin_ready()

    def test_explicit_enable_without_credentials_fails(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("ADMIN_ENABLED", "true")
        monkeypatch.delenv("ADMIN_USERS_JSON", raising=False)
        monkeypatch.delenv("ADMIN_USERNAME", raising=False)
        monkeypatch.delenv("ADMIN_PASSWORD_HASH", raising=False)
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        with pytest.raises(AdminConfigError):
            get_admin_config()

    def test_plaintext_password_rejected_in_production(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("ADMIN_USERNAME", "admin")
        monkeypatch.setenv("ADMIN_PASSWORD", "plaintext-password")
        monkeypatch.setenv("ADMIN_TOKEN_SECRET", "x" * 64)
        monkeypatch.delenv("ADMIN_PASSWORD_HASH", raising=False)
        monkeypatch.delenv("ADMIN_USERS_JSON", raising=False)
        with pytest.raises(AdminConfigError, match="ADMIN_PASSWORD"):
            get_admin_config()

    def test_disabled_surface_returns_503(self, monkeypatch, admin_client):
        monkeypatch.setenv("ADMIN_ENABLED", "false")
        response = admin_client.post(
            "/api/v1/admin/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        assert response.status_code == 503
        assert response.json()["code"] == "ADMIN_NOT_CONFIGURED"
