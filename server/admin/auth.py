"""Administrator authentication and role-based access control.

This module is deliberately separate from :mod:`server.auth`:

* the existing HMAC session token proves ownership of an anonymous chat
  session; it carries no account, role or expiry and **must never** grant
  administrative access;
* administrator credentials are injected from the environment, never
  hard-coded, and production startup fails closed when administration is
  explicitly enabled without a separate signing secret;
* tokens are scoped to ``aud=gaobao-admin`` and are signed with
  ``ADMIN_TOKEN_SECRET`` (or a domain-separated derivation in development).

Roles use a small hierarchy: ``viewer`` < ``operator`` < ``admin``.
"""

from __future__ import annotations

import base64
import binascii
import datetime
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from server.admin.client_ip import resolve_client_ip
from server.admin.errors import AdminError
from server.admin.revocation import hash_jti, is_token_revoked
from server.deps import get_db

logger = logging.getLogger(__name__)

Role = Literal["viewer", "operator", "admin"]

ROLE_LEVELS: dict[str, int] = {"viewer": 1, "operator": 2, "admin": 3}
_VALID_ROLES = frozenset(ROLE_LEVELS)
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.@-]{3,64}$")
_HASH_RE = re.compile(r"^pbkdf2_sha256\$(\d{5,7})\$([0-9a-f]{16,64})\$([0-9a-f]{64})$")
_JTI_RE = re.compile(r"^[0-9a-f]{16}$")
_TOKEN_PREFIX = "v1"
_TOKEN_AUDIENCE = "gaobao-admin"
_PBKDF2_ITERATIONS = 600_000
_DUMMY_SALT = b"gaobao-admin-timing-salt-v1"


class AdminConfigError(RuntimeError):
    """Raised when administrator configuration is invalid or unsafe."""


@dataclass(frozen=True)
class AdminUserConfig:
    username: str
    password_hash: str
    role: Role


@dataclass(frozen=True)
class AdminConfig:
    enabled: bool
    users: tuple[AdminUserConfig, ...]
    token_secret: bytes
    token_ttl_seconds: int
    source: str

    def find_user(self, username: str) -> AdminUserConfig | None:
        for user in self.users:
            if hmac.compare_digest(user.username, username):
                return user
        return None


@dataclass(frozen=True)
class AdminPrincipal:
    username: str
    role: Role
    jti_hash: str | None = None
    expires_at: int | None = None

    @property
    def level(self) -> int:
        return ROLE_LEVELS[self.role]


def _env_bool(name: str) -> str:
    return os.getenv(name, "auto").strip().lower()


def hash_password(password: str, *, iterations: int = _PBKDF2_ITERATIONS, salt: bytes | None = None) -> str:
    """Hash an administrator password using PBKDF2-HMAC-SHA256."""
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("administrator password must be at least 8 characters")
    if len(password) > 256:
        raise ValueError("administrator password is too long")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time verification of a PBKDF2 password hash."""
    try:
        match = _HASH_RE.match(encoded)
        if not match:
            return False
        iterations = int(match.group(1))
        if iterations < 10_000 or iterations > 2_000_000:
            return False
        salt = bytes.fromhex(match.group(2))
        expected = bytes.fromhex(match.group(3))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _burn_time(password: str) -> None:
    """Perform a dummy PBKDF2 round for unknown users (timing equalisation)."""
    hashlib.pbkdf2_hmac("sha256", password.encode("utf-8", "ignore"), _DUMMY_SALT, _PBKDF2_ITERATIONS)


def _parse_users(raw: str) -> tuple[AdminUserConfig, ...]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AdminConfigError("ADMIN_USERS_JSON is not valid JSON") from exc
    if not isinstance(data, list) or not data:
        raise AdminConfigError("ADMIN_USERS_JSON must be a non-empty JSON array")
    users: list[AdminUserConfig] = []
    seen: set[str] = set()
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise AdminConfigError(f"ADMIN_USERS_JSON[{index}] must be an object")
        username = str(item.get("username", "")).strip()
        password_hash = str(item.get("password_hash", "")).strip()
        role = str(item.get("role", "")).strip()
        if not _USERNAME_RE.match(username):
            raise AdminConfigError(f"ADMIN_USERS_JSON[{index}].username is invalid")
        if username in seen:
            raise AdminConfigError(f"duplicate administrator username: {username}")
        if not _HASH_RE.match(password_hash):
            raise AdminConfigError(
                f"ADMIN_USERS_JSON[{index}].password_hash must be generated by scripts/hash_admin_password.py"
            )
        if role not in _VALID_ROLES:
            raise AdminConfigError(f"ADMIN_USERS_JSON[{index}].role must be one of {sorted(_VALID_ROLES)}")
        seen.add(username)
        users.append(AdminUserConfig(username=username, password_hash=password_hash, role=role))  # type: ignore[arg-type]
    return tuple(users)


def _legacy_user_from_env() -> tuple[AdminUserConfig, ...]:
    """Single-user fallback for local development and small deployments."""
    username = os.getenv("ADMIN_USERNAME", "").strip()
    password_hash = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
    plaintext = os.getenv("ADMIN_PASSWORD", "")
    role = os.getenv("ADMIN_ROLE", "admin").strip() or "admin"
    env = os.getenv("APP_ENV", "development").strip().lower()

    if plaintext and env == "production":
        raise AdminConfigError("ADMIN_PASSWORD is not allowed in production; set ADMIN_PASSWORD_HASH")
    if plaintext and not password_hash:
        password_hash = hash_password(plaintext)
        logger.warning("ADMIN_PASSWORD was hashed in memory; prefer ADMIN_PASSWORD_HASH for reproducibility")
    if not username or not password_hash:
        return ()
    if not _USERNAME_RE.match(username):
        raise AdminConfigError("ADMIN_USERNAME is invalid")
    if role not in _VALID_ROLES:
        raise AdminConfigError(f"ADMIN_ROLE must be one of {sorted(_VALID_ROLES)}")
    if not _HASH_RE.match(password_hash):
        raise AdminConfigError("ADMIN_PASSWORD_HASH must be generated by scripts/hash_admin_password.py")
    return (AdminUserConfig(username=username, password_hash=password_hash, role=role),)  # type: ignore[arg-type]


def _token_secret(users: tuple[AdminUserConfig, ...]) -> bytes:
    explicit = os.getenv("ADMIN_TOKEN_SECRET", "").strip()
    env = os.getenv("APP_ENV", "development").strip().lower()
    if explicit:
        if len(explicit) < 32:
            raise AdminConfigError("ADMIN_TOKEN_SECRET must be at least 32 characters")
        return explicit.encode("utf-8")
    if not users:
        return b""
    if env == "production":
        raise AdminConfigError("ADMIN_TOKEN_SECRET must be set in production when administrators are configured")
    # Development only: derive a domain-separated secret from the session
    # secret so anonymous session tokens can never be replayed as admin tokens.
    try:
        from server.auth import _get_secret

        return hmac.new(_get_secret(), b"gaobao-admin-token-v1", hashlib.sha256).digest()
    except Exception as exc:  # pragma: no cover - defensive
        raise AdminConfigError("could not derive a development admin token secret") from exc


def get_admin_config() -> AdminConfig:
    """Load administrator configuration from the environment.

    Configuration is read on every call so tests and process managers can
    change it without stale module-level caches. Values are cheap to parse.
    """
    enabled_flag = _env_bool("ADMIN_ENABLED")
    raw_users = os.getenv("ADMIN_USERS_JSON", "").strip()
    users: tuple[AdminUserConfig, ...]
    source = "disabled"
    if raw_users:
        users = _parse_users(raw_users)
        source = "ADMIN_USERS_JSON"
    else:
        users = _legacy_user_from_env()
        source = "ADMIN_USERNAME" if users else "disabled"

    if enabled_flag in {"false", "0", "no", "off"}:
        return AdminConfig(False, (), b"", 0, "disabled")

    enabled = bool(users)
    if enabled_flag in {"true", "1", "yes", "on"} and not users:
        raise AdminConfigError("ADMIN_ENABLED=true but no administrator credentials are configured")

    ttl_raw = os.getenv("ADMIN_TOKEN_TTL_SECONDS", "28800")
    try:
        ttl = int(ttl_raw)
    except ValueError as exc:
        raise AdminConfigError("ADMIN_TOKEN_TTL_SECONDS must be an integer") from exc
    ttl = max(300, min(ttl, 86_400))

    return AdminConfig(
        enabled=enabled,
        users=users,
        token_secret=_token_secret(users),
        token_ttl_seconds=ttl if enabled else 0,
        source=source,
    )


def ensure_admin_ready() -> None:
    """Fail startup for an explicitly enabled but unsafe configuration.

    A production deployment with no administrator configured simply has the
    admin surface disabled (deny-all, fail closed). A production deployment
    that *does* configure administrators but omits the separate signing secret
    is a misconfiguration and must not start.
    """
    config = get_admin_config()
    if config.enabled and not config.token_secret:
        raise AdminConfigError("administrator token secret is missing")
    if config.enabled:
        from server.admin.limits import security_backend

        if os.getenv("APP_ENV", "development").strip().lower() == "production" and security_backend() != "redis":
            raise AdminConfigError(
                "production administrator rate limiting requires Redis; "
                "set REDIS_URL and ADMIN_RATE_LIMIT_BACKEND=redis (memory is not allowed in production)"
            )
        logger.info("admin surface enabled (%d user(s), source=%s)", len(config.users), config.source)


def authenticate(username: str, password: str) -> AdminPrincipal | None:
    config = get_admin_config()
    if not config.enabled:
        return None
    user = config.find_user(username)
    if user is None:
        _burn_time(password)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return AdminPrincipal(username=user.username, role=user.role)


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def issue_admin_token(principal: AdminPrincipal, *, now: int | None = None) -> tuple[str, int]:
    config = get_admin_config()
    if not config.enabled or not config.token_secret:
        raise AdminConfigError("administrator authentication is not configured")
    issued_at = int(time.time() if now is None else now)
    expires_in = config.token_ttl_seconds
    payload = {
        "aud": _TOKEN_AUDIENCE,
        "sub": principal.username,
        "role": principal.role,
        "iat": issued_at,
        "exp": issued_at + expires_in,
        "jti": secrets.token_hex(8),
    }
    body = _b64e(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    signing_input = f"{_TOKEN_PREFIX}.{body}".encode("ascii")
    signature = hmac.new(config.token_secret, signing_input, hashlib.sha256).digest()
    return f"{_TOKEN_PREFIX}.{body}.{_b64e(signature)}", expires_in


def verify_admin_token(token: str | None, *, now: int | None = None) -> AdminPrincipal | None:
    if not token:
        return None
    try:
        config = get_admin_config()
        if not config.enabled or not config.token_secret:
            return None
        parts = token.split(".")
        if len(parts) != 3 or parts[0] != _TOKEN_PREFIX:
            return None
        body = parts[1]
        expected = hmac.new(
            config.token_secret,
            f"{_TOKEN_PREFIX}.{body}".encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected, _b64d(parts[2])):
            return None
        payload: Any = json.loads(_b64d(body))
        if not isinstance(payload, dict) or payload.get("aud") != _TOKEN_AUDIENCE:
            return None
        expiry = int(payload.get("exp", 0))
        if expiry <= int(time.time() if now is None else now):
            return None
        jti = str(payload.get("jti", ""))
        if not _JTI_RE.match(jti):
            return None
        username = str(payload.get("sub", ""))
        user = config.find_user(username)
        if user is None:
            return None
        # Use the *current* configured role, not the role embedded at issue
        # time: demoting/removing a user takes effect on the next request.
        return AdminPrincipal(
            username=user.username,
            role=user.role,
            jti_hash=hash_jti(jti, config.token_secret),
            expires_at=expiry,
        )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, binascii.Error):
        return None


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return value.strip() or None


def require_role(minimum: Role, *, allow_revoked: bool = False) -> Callable[..., AdminPrincipal]:
    """FastAPI dependency factory enforcing an administrator role floor.

    Revocation is checked against the database after signature/claims/role
    validation. ``allow_revoked`` is only used by logout so repeated logout is
    idempotent while every other endpoint rejects the revoked token.
    """

    required_level = ROLE_LEVELS[minimum]

    async def dependency(
        authorization: str | None = Header(default=None),
        db: Session = Depends(get_db),
    ) -> AdminPrincipal:
        config_error: AdminConfigError | None = None
        try:
            config = get_admin_config()
        except AdminConfigError as exc:
            config = None
            config_error = exc
        if config_error is not None:
            raise HTTPException(status_code=503, detail="Admin authentication is not configured") from config_error
        if config is None or not config.enabled:
            raise HTTPException(status_code=503, detail="Admin authentication is not configured")
        token = _bearer(authorization)
        if token is None:
            raise HTTPException(status_code=401, detail="Missing administrator token")
        principal = verify_admin_token(token)
        if principal is None:
            raise HTTPException(status_code=401, detail="Invalid or expired administrator token")
        if principal.level < required_level:
            raise HTTPException(status_code=403, detail="Insufficient administrator role")
        if principal.jti_hash is None or principal.expires_at is None:
            raise HTTPException(status_code=401, detail="Invalid administrator token claims")
        if not allow_revoked and is_token_revoked(db, principal.jti_hash):
            raise AdminError(401, "ADMIN_TOKEN_REVOKED", "管理员 Token 已被撤销")
        return principal

    return dependency


def token_expiry_datetime(principal: AdminPrincipal) -> datetime.datetime:
    if principal.expires_at is None:
        raise ValueError("administrator token has no expiry")
    return datetime.datetime.fromtimestamp(principal.expires_at, tz=datetime.timezone.utc).replace(tzinfo=None)


def client_ip_hash(request: Request) -> str:
    """Hash the normalized client address; never store the raw address."""
    ip = resolve_client_ip(request)
    try:
        secret = get_admin_config().token_secret or b"gaobao-audit"
    except AdminConfigError:
        secret = b"gaobao-audit"
    return hmac.new(secret, ip.encode("utf-8", "ignore"), hashlib.sha256).hexdigest()[:32]
