"""Privacy-safe helpers for operational logging."""

from __future__ import annotations

import hashlib


def safe_log_reference(value: object) -> str:
    """Return a stable pseudonymous reference without logging the raw value."""
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]
    return f"ref-{digest}"


def safe_exception_name(error: BaseException) -> str:
    """Describe an operational failure without serializing sensitive arguments."""
    return type(error).__name__
