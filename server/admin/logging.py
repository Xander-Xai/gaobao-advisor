"""Structured logging helpers for administrative operations."""

from __future__ import annotations

import json
import logging
from typing import Any

from server.middleware.request_id import get_request_id

logger = logging.getLogger("server.admin")


def log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, "request_id": get_request_id(), **fields}
    logger.info(json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True))


def log_warning(event: str, **fields: Any) -> None:
    payload = {"event": event, "request_id": get_request_id(), **fields}
    logger.warning(json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True))


def log_error(event: str, **fields: Any) -> None:
    payload = {"event": event, "request_id": get_request_id(), **fields}
    logger.error(json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True))
