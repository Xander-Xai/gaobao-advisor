"""Session HMAC token authentication — lightweight session ownership proof.

No full auth system needed: the client receives a signed token on first
contact and must present it on subsequent requests. Prevents session_id
enumeration attacks.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets

logger = logging.getLogger(__name__)

_SECRET = os.getenv("SESSION_SECRET", "")


def _get_secret() -> bytes:
    """Return the HMAC signing secret, generating one if not configured."""
    global _SECRET
    if not _SECRET:
        _SECRET = secrets.token_hex(32)
        logger.warning(
            "SESSION_SECRET not set — using ephemeral random secret. "
            "Session tokens will be invalidated on restart. "
            "Set SESSION_SECRET in .env for production."
        )
    return _SECRET.encode()


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
