"""Minimal Redis-backed queue for data-quality jobs.

Design notes:

* one queue, one job type — deliberately not a general-purpose broker;
* the database is the source of truth for job state; Redis only carries the
  job id;
* publishing is protected by a transactional outbox (see
  :func:`dispatch_outbox`), so a Redis outage cannot lose an accepted job;
* a missing ``REDIS_URL`` disables the queue instead of silently pretending a
  job was dispatched.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_KEY = "gaobao:quality:jobs"


class QueueUnavailable(RuntimeError):
    """Redis is configured but unreachable, or the client is not installed."""


class RedisQueue:
    def __init__(self, *, url: str | None = None, key: str | None = None, client: Any | None = None) -> None:
        self.url = url or os.getenv("REDIS_URL", "").strip()
        self.key = key or os.getenv("QUALITY_QUEUE_KEY", DEFAULT_QUEUE_KEY).strip() or DEFAULT_QUEUE_KEY
        self._client = client
        self._connected = client is not None

    def _connect(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.url:
            raise QueueUnavailable("REDIS_URL is not configured")
        try:
            import redis
        except ImportError as exc:  # pragma: no cover - dependency is optional
            raise QueueUnavailable("redis package is not installed") from exc
        try:
            client = redis.Redis.from_url(
                self.url,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=2,
            )
            client.ping()
        except Exception as exc:
            raise QueueUnavailable("Redis is unreachable") from exc
        self._client = client
        self._connected = True
        return client

    def ping(self) -> bool:
        try:
            self._connect().ping()
            return True
        except QueueUnavailable:
            return False
        except Exception:
            self._connected = False
            self._client = None
            return False

    def enqueue(self, job_id: int) -> None:
        client = self._connect()
        try:
            client.lpush(self.key, str(job_id))
        except Exception as exc:
            self._connected = False
            self._client = None
            raise QueueUnavailable("failed to enqueue quality job") from exc

    def dequeue(self, timeout: int = 2) -> int | None:
        client = self._connect()
        try:
            item = client.brpop(self.key, timeout=timeout)
        except Exception as exc:
            self._connected = False
            self._client = None
            raise QueueUnavailable("failed to read quality job") from exc
        if not item:
            return None
        try:
            return int(item[1])
        except (TypeError, ValueError):
            logger.error("discarding malformed queue payload: %r", item)
            return None

    def depth(self) -> int:
        return int(self._connect().llen(self.key))

    def close(self) -> None:
        client = self._client
        self._client = None
        self._connected = False
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def get_queue() -> RedisQueue | None:
    """Return a queue when Redis is configured; otherwise ``None``."""
    if not os.getenv("REDIS_URL", "").strip():
        return None
    return RedisQueue()


def queue_state(queue: RedisQueue | None = None) -> str:
    if queue is None:
        return "DISABLED"
    return "READY" if queue.ping() else "UNAVAILABLE"


def dispatch_outbox(*, job_id: int | None = None, limit: int = 20, queue: RedisQueue | None = None) -> dict[str, int]:
    """Publish pending outbox rows, updating their delivery state.

    Safe to call from the API after commit and from the worker periodically.
    A failure leaves the outbox row ``PENDING`` with backoff instead of marking
    the job successful.
    """
    from db.database import SessionLocal
    from server.admin import repository

    active_queue = queue or get_queue()
    result = {"published": 0, "failed": 0, "skipped": 1 if active_queue is None else 0}
    if active_queue is None:
        return result

    session = SessionLocal()
    try:
        rows = repository.pending_outbox(session, limit=limit, job_id=job_id)
        if not rows:
            return result
        for row in rows:
            try:
                active_queue.enqueue(row.job_id)
            except QueueUnavailable as exc:
                repository.mark_outbox_failed(session, row.job_id, str(exc))
                result["failed"] += 1
            else:
                repository.mark_outbox_dispatched(session, row.job_id)
                result["published"] += 1
    finally:
        session.close()
    return result


def delete_queue(queue: RedisQueue) -> None:
    """Best-effort queue cleanup used by tests and demos."""
    try:
        queue._connect().delete(queue.key)  # noqa: SLF001 - intentional maintenance helper
    except Exception:
        pass
