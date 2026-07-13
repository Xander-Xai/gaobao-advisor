"""Session HMAC token authentication — lightweight session ownership proof.

No full auth system needed: the client receives a signed token on first
contact and must present it on subsequent requests. Prevents session_id
enumeration attacks.

Production requirement: SESSION_SECRET must be set explicitly.
When running with multiple workers (gunicorn/uvicorn workers > 1),
each worker must share the same SESSION_SECRET or session tokens
will fail verification across workers.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets

from config.loader import load_runtime_settings

logger = logging.getLogger(__name__)

_SECRET: str | None = None


def _get_secret() -> bytes:
    """Return the HMAC signing secret."""
    global _SECRET
    if _SECRET is None:
        _SECRET = os.getenv("SESSION_SECRET", "")
        if not _SECRET:
            _SECRET = _load_or_generate_secret()
    return _SECRET.encode()


def _load_or_generate_secret() -> str:
    """Load secret from file or generate a new one.

    In production (APP_ENV=production), missing SESSION_SECRET is fatal.
    In development, persist generated secret to data/.session_secret
    so multiple restarts share the same key.
    """
    env = os.getenv("APP_ENV", "development")
    secret_file = load_runtime_settings()["session_secret_file"]

    # Try to load existing secret from file
    if os.path.exists(secret_file):
        with open(secret_file, encoding="utf-8") as f:
            secret = f.read().strip()
        if secret:
            logger.info("Loaded session secret from %s", secret_file)
            return secret

    # Production: must have explicit SESSION_SECRET
    if env == "production":
        raise RuntimeError(
            "SESSION_SECRET must be set in production. Set it via environment variable before starting the server."
        )

    # Development: generate and persist
    secret = secrets.token_hex(32)
    try:
        os.makedirs(os.path.dirname(secret_file), exist_ok=True)
        with open(secret_file, "w", encoding="utf-8") as f:
            f.write(secret)
        os.chmod(secret_file, 0o600)
        logger.warning(
            "SESSION_SECRET not set — generated ephemeral secret at %s. Set SESSION_SECRET in .env for production.",
            secret_file,
        )
    except OSError as e:
        logger.warning("Could not persist session secret: %s", e)
    return secret


def create_session_token(session_id: str) -> str:
    """Create an HMAC-SHA256 token for the given session_id."""
    secret = _get_secret()
    return hmac.new(secret, session_id.encode(), hashlib.sha256).hexdigest()


def verify_session_token(session_id: str, token: str | None) -> bool:
    """Verify the token matches the session_id. Returns False on any error."""
    if not session_id or not token:
        return False
    try:
        expected = create_session_token(session_id)
        return hmac.compare_digest(expected, token)
    except Exception:
        return False


def require_bearer_auth(session_id: str, authorization: str | None = None) -> None:
    """Validate session ownership via Bearer token. Raises 401 on failure."""
    from fastapi import HTTPException

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing session token")
    token = authorization.removeprefix("Bearer ").strip()
    if not verify_session_token(session_id, token):
        raise HTTPException(status_code=401, detail="Invalid or expired session token")


def require_token_auth(session_id: str, token: str | None = None) -> None:
    """Validate session ownership via direct token. Raises 403 on failure."""
    from fastapi import HTTPException
    from starlette.status import HTTP_403_FORBIDDEN

    if not session_id:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Missing session_id")
    if not token:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Missing authentication token")
    if not verify_session_token(session_id, token):
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid authentication token")
