"""Redis delivery-adapter tests for the Issue #40 experiment.

These are real-Redis integration tests and do not touch MySQL. They verify the
ACK and pending-entry mechanics used by the comparison harness.
"""

from __future__ import annotations

import os
import time
import uuid

import pytest

from benchmarks.queue_recovery.adapters import BLMOVEAdapter, ListOutboxAdapter, StreamsAdapter
from benchmarks.queue_recovery.metrics import percentile, summarize

REDIS_URL = os.getenv("REDIS_TEST_URL", "").strip()
pytestmark = [pytest.mark.redis, pytest.mark.skipif(not REDIS_URL, reason="REDIS_TEST_URL is required")]


def _cleanup_keys(adapter, *keys: str) -> None:
    try:
        adapter.client.delete(*keys)
    except Exception:
        pass


def test_list_adapter_roundtrip():
    adapter = ListOutboxAdapter(REDIS_URL, run_id=uuid.uuid4().hex)
    try:
        adapter.publish(42)
        delivery = adapter.consume_one(timeout=1)
        assert delivery is not None and delivery.job_id == 42
        adapter.ack(delivery)
        assert adapter.depth() == 0
    finally:
        adapter.queue._connect().delete(adapter.queue.key)  # noqa: SLF001 - test cleanup
        adapter.close()


def test_blmove_ack_removes_processing_entry():
    adapter = BLMOVEAdapter(REDIS_URL, run_id=uuid.uuid4().hex)
    try:
        adapter.publish(7)
        delivery = adapter.consume_one(timeout=1)
        assert delivery is not None and delivery.job_id == 7
        assert adapter.sizes()["processing"] == 1
        adapter.ack(delivery)
        assert adapter.pending_count() == 0
    finally:
        _cleanup_keys(adapter, adapter.ready, adapter.processing, adapter.started)
        adapter.close()


def test_blmove_stale_entry_can_be_requeued():
    adapter = BLMOVEAdapter(REDIS_URL, run_id=uuid.uuid4().hex)
    try:
        adapter.publish(8)
        delivery = adapter.consume_one(timeout=1)
        assert delivery is not None
        time.sleep(1.1)
        stale = adapter.stale(lease_seconds=1.0)
        assert [item.job_id for item in stale] == [8]
        adapter.requeue(stale[0])
        assert adapter.sizes()["processing"] == 0
        assert adapter.consume_one(timeout=1).job_id == 8
    finally:
        _cleanup_keys(adapter, adapter.ready, adapter.processing, adapter.started)
        adapter.close()


def test_streams_ack_clears_pending_entry():
    adapter = StreamsAdapter(REDIS_URL, run_id=uuid.uuid4().hex, consumer="test-consumer")
    try:
        adapter.publish(9)
        delivery = adapter.consume_one(timeout=1)
        assert delivery is not None and delivery.job_id == 9
        assert adapter.pending_count() == 1
        adapter.ack(delivery)
        assert adapter.pending_count() == 0
    finally:
        _cleanup_keys(adapter, adapter.stream)
        adapter.close()


def test_streams_pending_entry_is_claimable_after_lease():
    adapter = StreamsAdapter(REDIS_URL, run_id=uuid.uuid4().hex, consumer="test-consumer")
    try:
        adapter.publish(10)
        delivery = adapter.consume_one(timeout=1)
        assert delivery is not None
        time.sleep(1.1)
        stale = adapter.stale(lease_seconds=1.0)
        assert [item.job_id for item in stale] == [10]
        adapter.discard(stale[0])
        assert adapter.pending_count() == 0
    finally:
        _cleanup_keys(adapter, adapter.stream)
        adapter.close()


def test_percentiles_are_monotonic():
    assert percentile([1.0, 2.0, 3.0, 4.0, 5.0], 0.50) == 3.0
    assert summarize([1.0, 2.0, 3.0, 4.0, 5.0])["p95"] == 5.0
