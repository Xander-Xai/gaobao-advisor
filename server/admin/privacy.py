"""Small, auditable redaction helpers for demo and audit payloads.

This is intentionally not a general DLP product. It covers the identifiers the
demo actually uses (student names, phone numbers, ID cards, e-mail, tokens) and
is applied to audit detail before persistence.
"""

from __future__ import annotations

import re
from typing import Any

_PHONE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
_ID_CARD = re.compile(r"(?<!\d)(\d{6})\d{8}(\d{3}[\dXx])(?!\d)")
_EMAIL = re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_TOKEN = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._~+/=-]{8,}")
_API_KEY = re.compile(r"\b(sk-[A-Za-z0-9_-]{8,})")
_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
    "session_token",
    "phone",
    "mobile",
    "id_card",
    "idcard",
    "email",
    "student_name",
    "name",
}
_NAME_KEYS = {"student_name", "name", "real_name", "candidate_name"}


def mask_name(value: str) -> str:
    value = value.strip()
    if not value:
        return value
    if len(value) == 1:
        return "*"
    if len(value) == 2:
        return value[0] + "*"
    return value[0] + "*" * (len(value) - 2) + value[-1]


def mask_phone(value: str) -> str:
    match = _PHONE.search(value)
    if not match:
        return value
    phone = match.group(1)
    return value.replace(phone, phone[:3] + "****" + phone[-4:])


def mask_id_card(value: str) -> str:
    return _ID_CARD.sub(lambda m: m.group(1) + "*" * 8 + m.group(2), value)


def mask_email(value: str) -> str:
    return _EMAIL.sub(lambda m: m.group(1) + "***" + m.group(2), value)


def redact_sensitive_text(value: str) -> str:
    value = _TOKEN.sub(lambda m: m.group(1) + "***", value)
    value = _API_KEY.sub("sk-***", value)
    value = mask_phone(value)
    value = mask_id_card(value)
    value = mask_email(value)
    return value


def sanitize_detail(value: Any, *, key: str = "") -> Any:
    """Recursively redact audit metadata before it is persisted."""
    lowered = key.lower()
    if isinstance(value, dict):
        return {str(k): sanitize_detail(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize_detail(item, key=key) for item in value]
    if isinstance(value, str):
        if lowered in _NAME_KEYS:
            return mask_name(value)
        if lowered in _SENSITIVE_KEYS:
            return "***"
        return redact_sensitive_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact_sensitive_text(str(value))
