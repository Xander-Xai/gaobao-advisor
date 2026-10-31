"""Administrator security: revocation, trusted proxies and fail-closed limits."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from server.admin.auth import (
    AdminConfigError,
    ensure_admin_ready,
    get_admin_config,
    hash_password,
    verify_admin_token,
)
from server.admin.client_ip import resolve_client_ip
from server.admin.limits import AdminLimiter
from server.admin.routes import _job_limiter, _login_limiter
from server.deps import get_db
from server.main import app
from tests.conftest import ADMIN_PASSWORD, auth_header, login


def _request(peer: str, forwarded: str | None = None) -> Request:
    headers = []
    if forwarded is not None:
        headers.append((b"x-forwarded-for", forwarded.encode("ascii")))
    return Request({"type": "http", "client": (peer, 12345), "headers": headers, "method": "GET", "path": "/"})


class TestTrustedProxy:
    def test_forwarded_for_is_ignored_by_default(self, monkeypatch):
        monkeypatch.delenv("ADMIN_TRUSTED_PROXIES", raising=False)
        assert resolve_client_ip(_request("203.0.113.9", "198.51.100.1")) == "203.0.113.9"

    def test_only_trusted_peer_uses_forwarded_chain(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TRUSTED_PROXIES", "10.0.0.0/8")
        assert resolve_client_ip(_request("203.0.113.9", "198.51.100.1")) == "203.0.113.9"
        assert resolve_client_ip(_request("10.1.2.3", "198.51.100.1, 10.1.2.3")) == "198.51.100.1"

    def test_rightmost_untrusted_hop_wins_over_spoofed_leftmost(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TRUSTED_PROXIES", "10.0.0.0/8")
        assert resolve_client_ip(_request("10.1.2.3", "1.2.3.4, 198.51.100.1, 10.1.2.3")) == "198.51.100.1"

    def test_invalid_forwarded_value_falls_back_to_peer(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TRUSTED_PROXIES", "10.0.0.0/8")
        assert resolve_client_ip(_request("10.1.2.3", "not-an-ip, 10.1.2.3")) == "10.1.2.3"

    def test_ipv6_and_mapped_ipv4_are_normalized(self, monkeypatch):
        monkeypatch.setenv("ADMIN_TRUSTED_PROXIES", "::1/128")
        assert resolve_client_ip(_request("::1", "2001:db8::1, ::1")) == "2001:db8::1"
        assert resolve_client_ip(_request("::ffff:127.0.0.1", "198.51.100.7")) == "127.0.0.1"


class TestLogoutAndRevocation:
    def test_logout_revokes_token_and_is_idempotent(self, admin_client):
        token = login(admin_client, "admin")
        headers = auth_header(token)
        assert admin_client.get("/api/v1/admin/auth/me", headers=headers).status_code == 200

        first = admin_client.post("/api/v1/admin/auth/logout", headers=headers)
        assert first.status_code == 204
        revoked = admin_client.get("/api/v1/admin/auth/me", headers=headers)
        assert revoked.status_code == 401
        assert revoked.json()["code"] == "ADMIN_TOKEN_REVOKED"

        second = admin_client.post("/api/v1/admin/auth/logout", headers=headers)
        assert second.status_code == 204

    def test_other_tokens_survive_logout(self, admin_client):
        first_token = login(admin_client, "admin")
        second_token = login(admin_client, "admin")
        assert admin_client.post("/api/v1/admin/auth/logout", headers=auth_header(first_token)).status_code == 204
        assert admin_client.get("/api/v1/admin/auth/me", headers=auth_header(first_token)).status_code == 401
        assert admin_client.get("/api/v1/admin/auth/me", headers=auth_header(second_token)).status_code == 200

    def test_logout_writes_audit_without_token(self, admin_client):
        token = login(admin_client, "admin")
        assert admin_client.post("/api/v1/admin/auth/logout", headers=auth_header(token)).status_code == 204
        logs = admin_client.get("/api/v1/admin/audit-logs", headers=auth_header(login(admin_client, "admin")))
        assert logs.status_code == 200
        logout_logs = [item for item in logs.json()["items"] if item["action"] == "admin.logout"]
        assert logout_logs
        assert token not in json.dumps(logout_logs)

    def test_expired_token_is_rejected_at_exp_boundary(self, admin_client):
        token = login(admin_client, "admin")
        payload = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
        assert verify_admin_token(token, now=payload["exp"] - 1) is not None
        assert verify_admin_token(token, now=payload["exp"]) is None

    def test_deleted_admin_and_role_downgrade_take_effect(self, admin_client, monkeypatch):
        token = login(admin_client, "admin")
        config = get_admin_config()
        downgraded = [
            {
                "username": user.username,
                "password_hash": user.password_hash,
                "role": "viewer" if user.username == "admin" else user.role,
            }
            for user in config.users
        ]
        monkeypatch.setenv("ADMIN_USERS_JSON", json.dumps(downgraded))
        assert verify_admin_token(token).role == "viewer"
        remaining = [user for user in downgraded if user["username"] != "admin"]
        monkeypatch.setenv("ADMIN_USERS_JSON", json.dumps(remaining))
        assert verify_admin_token(token) is None

    @staticmethod
    def _resign(payload: dict) -> str:
        secret = get_admin_config().token_secret
        body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=").decode()
        signature = hmac.new(secret, f"v1.{body}".encode("ascii"), hashlib.sha256).digest()
        return f"v1.{body}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"

    def test_missing_or_invalid_jti_is_rejected(self, admin_client):
        token = login(admin_client, "admin")
        body = token.split(".")[1]
        payload = json.loads(base64.urlsafe_b64decode(body + "=="))
        payload.pop("jti")
        assert verify_admin_token(self._resign(payload)) is None
        payload["jti"] = "not-a-valid-jti"
        assert verify_admin_token(self._resign(payload)) is None

    def test_audience_mismatch_is_rejected(self, admin_client):
        token = login(admin_client, "admin")
        payload = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
        payload["aud"] = "not-admin"
        assert verify_admin_token(self._resign(payload)) is None


class TestRateLimitRoutes:
    def test_login_rate_limit_has_retry_after_and_same_message(self, admin_client):
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
        assert int(blocked.headers["Retry-After"]) >= 1
        assert "用户名或密码错误" not in blocked.text

    def test_username_dimension_limits_multi_ip_attempts(self, admin_factory, admin_env, monkeypatch):
        monkeypatch.setenv("ADMIN_TRUSTED_PROXIES", "127.0.0.1/32")
        monkeypatch.setenv("ADMIN_RATE_LIMIT_BACKEND", "memory")
        _login_limiter.reset()

        def override_get_db():
            session = admin_factory()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app, client=("127.0.0.1", 12345))
        try:
            for index in range(8):
                response = client.post(
                    "/api/v1/admin/auth/login",
                    json={"username": "admin", "password": "wrong-password-123"},
                    headers={"X-Forwarded-For": f"198.51.100.{index + 1}"},
                )
                assert response.status_code == 401
            blocked = client.post(
                "/api/v1/admin/auth/login",
                json={"username": "admin", "password": "wrong-password-123"},
                headers={"X-Forwarded-For": "203.0.113.1"},
            )
            assert blocked.status_code == 429
        finally:
            app.dependency_overrides.pop(get_db, None)
            client.close()

    def test_same_ip_multi_account_rotation_is_limited(self, admin_factory, admin_env, monkeypatch):
        monkeypatch.setenv("ADMIN_TRUSTED_PROXIES", "127.0.0.1/32")
        monkeypatch.setenv("ADMIN_RATE_LIMIT_BACKEND", "memory")
        _login_limiter.reset()

        def override_get_db():
            session = admin_factory()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app, client=("127.0.0.1", 12345))
        try:
            for index in range(8):
                username = "admin" if index % 2 == 0 else "operator"
                response = client.post(
                    "/api/v1/admin/auth/login",
                    json={"username": username, "password": "wrong-password-123"},
                    headers={"X-Forwarded-For": "198.51.100.50"},
                )
                assert response.status_code == 401
            blocked = client.post(
                "/api/v1/admin/auth/login",
                json={"username": "viewer", "password": "wrong-password-123"},
                headers={"X-Forwarded-For": "198.51.100.50"},
            )
            assert blocked.status_code == 429
        finally:
            app.dependency_overrides.pop(get_db, None)
            client.close()

    def test_revocation_is_visible_to_second_api_client(self, admin_factory, admin_env):
        def override_get_db():
            session = admin_factory()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        first = TestClient(app, client=("127.0.0.1", 10001))
        second = TestClient(app, client=("127.0.0.1", 10002))
        try:
            token = login(first, "admin")
            assert first.post("/api/v1/admin/auth/logout", headers=auth_header(token)).status_code == 204
            assert second.get("/api/v1/admin/auth/me", headers=auth_header(token)).status_code == 401
        finally:
            app.dependency_overrides.pop(get_db, None)
            first.close()
            second.close()

    def test_job_limiter_blocks_second_request_when_limit_is_one(self, admin_client, monkeypatch):
        token = login(admin_client, "operator")
        monkeypatch.setattr(_job_limiter, "limit", 1)
        monkeypatch.setattr(_job_limiter.memory, "limit", 1)
        first = admin_client.post(
            "/api/v1/admin/quality/jobs",
            json={"filters": {}},
            headers={**auth_header(token), "Idempotency-Key": "security-job-key-01"},
        )
        assert first.status_code in (200, 201, 202)
        second = admin_client.post(
            "/api/v1/admin/quality/jobs",
            json={"filters": {}},
            headers={**auth_header(token), "Idempotency-Key": "security-job-key-02"},
        )
        assert second.status_code == 429
        assert int(second.headers["Retry-After"]) >= 1

    def test_redis_backend_unavailable_is_503_not_429(self, admin_client, monkeypatch):
        monkeypatch.setenv("ADMIN_RATE_LIMIT_BACKEND", "redis")
        monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
        _login_limiter.reset()
        response = admin_client.post(
            "/api/v1/admin/auth/login",
            json={"username": "admin", "password": ADMIN_PASSWORD},
        )
        assert response.status_code == 503
        assert response.json()["code"] == "SECURITY_BACKEND_UNAVAILABLE"

    def test_production_memory_backend_fails_startup(self, monkeypatch):
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("ADMIN_RATE_LIMIT_BACKEND", "memory")
        monkeypatch.setenv("ADMIN_TOKEN_SECRET", "x" * 64)
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
        with pytest.raises(AdminConfigError, match="requires Redis"):
            ensure_admin_ready()


def test_admin_limiter_memory_dimensions_are_independent(monkeypatch):
    monkeypatch.setenv("ADMIN_RATE_LIMIT_BACKEND", "memory")
    monkeypatch.delenv("REDIS_URL", raising=False)
    limiter = AdminLimiter(scope="test", limit=1, window_seconds=60)
    limiter.reset()
    assert limiter.check("user:a")[0] is True
    assert limiter.check("user:b")[0] is True
    assert limiter.check("user:a")[0] is False
