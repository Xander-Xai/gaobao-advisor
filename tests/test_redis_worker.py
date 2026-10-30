"""Optional Redis + worker integration tests.

Run with a disposable Redis, e.g.::

    docker run --rm -d --name gaobao-redis-test -p 6380:6379 redis:7-alpine
    REDIS_TEST_URL=redis://127.0.0.1:6380/0 \\
      .venv/bin/python -m pytest tests/test_redis_worker.py -q
"""

from __future__ import annotations

import os
import uuid

import pytest

from db.models import DataQualityJob, QualityTaskOutbox
from server.admin import repository
from server.admin.queue import QueueUnavailable, RedisQueue, dispatch_outbox
from server.admin.worker import run_once

REDIS_TEST_URL = os.getenv("REDIS_TEST_URL", "").strip()
pytestmark = [
    pytest.mark.redis,
    pytest.mark.skipif(not REDIS_TEST_URL, reason="REDIS_TEST_URL is not set"),
]


@pytest.fixture
def redis_queue():
    queue = RedisQueue(url=REDIS_TEST_URL, key=f"gaobao:test:quality:{uuid.uuid4().hex}")
    if not queue.ping():
        pytest.skip("Redis is not reachable")
    try:
        yield queue
    finally:
        try:
            queue._connect().delete(queue.key)  # noqa: SLF001 - test cleanup
        finally:
            queue.close()


def test_redis_queue_enqueue_dequeue(redis_queue):
    redis_queue.enqueue(41)
    redis_queue.enqueue(42)
    assert redis_queue.depth() == 2
    assert redis_queue.dequeue(timeout=1) == 41
    assert redis_queue.dequeue(timeout=1) == 42
    assert redis_queue.dequeue(timeout=1) is None


def test_outbox_redis_worker_end_to_end(admin_factory, redis_queue, monkeypatch):
    session = admin_factory()
    try:
        job, _ = repository.create_job_with_outbox(
            session,
            filters={},
            idempotency_key="redis-e2e-key-0001",
            actor="operator",
            role="operator",
            request_id="req-redis-e2e",
            ip_hash=None,
        )
        job_id = job.id
    finally:
        session.close()

    monkeypatch.setattr("db.database.SessionLocal", admin_factory)
    result = dispatch_outbox(job_id=job_id, queue=redis_queue)
    assert result == {"published": 1, "failed": 0, "skipped": 0}

    session = admin_factory()
    try:
        processed = run_once(queue=redis_queue, db=session)
        job = session.get(DataQualityJob, job_id)
        outbox = session.query(QualityTaskOutbox).filter_by(job_id=job_id).one()
        assert processed["job_id"] == job_id
        assert processed["status"] == "SUCCEEDED"
        assert job.status == "SUCCEEDED"
        assert outbox.status == "DISPATCHED"
    finally:
        session.close()


def test_unreachable_redis_is_explicit():
    queue = RedisQueue(url="redis://127.0.0.1:1/0", key="gaobao:test:unreachable")
    assert queue.ping() is False
    with pytest.raises(QueueUnavailable):
        queue.enqueue(1)
    queue.close()
