"""Delivery adapters for the three Issue #40 candidates.

All adapters carry only a job id. MySQL remains the source of truth and the
same ``claim_job``/fencing path is used for every scheme. BLMOVE and Streams
are experiment adapters, not production wiring.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from benchmarks.queue_recovery.workload import QUEUE_PREFIX
from server.admin.queue import RedisQueue


@dataclass(frozen=True)
class Delivery:
    scheme: str
    job_id: int
    delivery_id: str
    raw: str | None = None
    message_id: str | None = None


class BaseAdapter:
    scheme = "base"

    def publish(self, job_id: int) -> Delivery:
        raise NotImplementedError

    def consume_one(self, timeout: int = 1) -> Delivery | None:
        raise NotImplementedError

    def ack(self, delivery: Delivery) -> None:
        raise NotImplementedError

    def stale(self, *, lease_seconds: float) -> list[Delivery]:
        return []

    def claim_stale(self, delivery: Delivery, *, lease_seconds: float) -> bool:
        return True

    def requeue(self, delivery: Delivery) -> None:
        raise NotImplementedError

    def discard(self, delivery: Delivery) -> None:
        raise NotImplementedError

    def pending_count(self) -> int:
        return 0

    def sizes(self) -> dict[str, int]:
        return {}

    def memory(self) -> dict[str, Any]:
        return {}

    def depth(self) -> int:
        return 0

    def close(self) -> None:
        pass


class ListOutboxAdapter(BaseAdapter):
    """Current production path: BRPOP + MySQL outbox compensation."""

    scheme = "list"

    def __init__(self, url: str, *, run_id: str) -> None:
        self.queue = RedisQueue(url=url, key=f"{QUEUE_PREFIX}:list:{run_id}")
        if not self.queue.ping():
            raise RuntimeError("Redis is unreachable for List adapter")

    def publish(self, job_id: int) -> Delivery:
        self.queue.enqueue(job_id)
        return Delivery(self.scheme, job_id, f"list-{uuid.uuid4().hex}")

    def consume_one(self, timeout: int = 1) -> Delivery | None:
        job_id = self.queue.dequeue(timeout=timeout)
        if job_id is None:
            return None
        return Delivery(self.scheme, job_id, f"list-{uuid.uuid4().hex}")

    def ack(self, delivery: Delivery) -> None:
        # BRPOP has already removed the message; the outbox/DB claim is the
        # acknowledgement boundary.
        return None

    def dispatch_due(self) -> dict[str, int]:
        from server.admin.queue import dispatch_outbox

        return dispatch_outbox(limit=50, queue=self.queue)

    def pending_count(self) -> int:
        return self.depth()

    def sizes(self) -> dict[str, int]:
        return {"ready": self.depth()}

    def memory(self) -> dict[str, Any]:
        info = self.queue._connect().info("memory")  # noqa: SLF001 - experiment metrics
        return {
            "used_memory_bytes": int(info.get("used_memory", 0)),
            "used_memory_human": str(info.get("used_memory_human", "")),
        }

    def depth(self) -> int:
        return self.queue.depth()

    def close(self) -> None:
        self.queue.close()


class BLMOVEAdapter(BaseAdapter):
    """Atomically move ready -> processing; ACK removes the processing entry.

    BLMOVE does not provide a consumer acknowledgement protocol. This adapter
    adds a per-delivery started timestamp and a recovery scan. The database
    claim/fencing remains the correctness boundary.
    """

    scheme = "blmove"

    def __init__(self, url: str, *, run_id: str) -> None:
        import redis

        self.client = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=1, socket_timeout=2)
        self.client.ping()
        self.ready = f"{QUEUE_PREFIX}:blmove:{run_id}:ready"
        self.processing = f"{QUEUE_PREFIX}:blmove:{run_id}:processing"
        self.started = f"{QUEUE_PREFIX}:blmove:{run_id}:started"

    @staticmethod
    def _payload(job_id: int, delivery_id: str) -> str:
        return json.dumps({"job_id": job_id, "delivery_id": delivery_id}, separators=(",", ":"))

    @staticmethod
    def _parse(raw: str) -> tuple[int, str]:
        value = json.loads(raw)
        return int(value["job_id"]), str(value["delivery_id"])

    def publish(self, job_id: int) -> Delivery:
        delivery_id = f"blmove-{uuid.uuid4().hex}"
        raw = self._payload(job_id, delivery_id)
        self.client.lpush(self.ready, raw)
        return Delivery(self.scheme, job_id, delivery_id, raw=raw)

    def consume_one(self, timeout: int = 1) -> Delivery | None:
        raw = self.client.blmove(self.ready, self.processing, timeout, "RIGHT", "LEFT")
        if raw is None:
            return None
        job_id, delivery_id = self._parse(raw)
        self.client.hset(self.started, delivery_id, str(time.time()))
        return Delivery(self.scheme, job_id, delivery_id, raw=raw)

    def ack(self, delivery: Delivery) -> None:
        if delivery.raw:
            self.client.lrem(self.processing, 1, delivery.raw)
        self.client.hdel(self.started, delivery.delivery_id)

    def stale(self, *, lease_seconds: float) -> list[Delivery]:
        now = time.time()
        stale: list[Delivery] = []
        for raw in self.client.lrange(self.processing, 0, -1):
            try:
                job_id, delivery_id = self._parse(raw)
            except Exception:
                # Malformed experiment payload: make it visible, do not crash
                # recovery. It cannot be mapped to a DB job.
                continue
            started = self.client.hget(self.started, delivery_id)
            age = now - float(started) if started else float("inf")
            if age >= lease_seconds:
                stale.append(Delivery(self.scheme, job_id, delivery_id, raw=raw))
        return stale

    def claim_stale(self, delivery: Delivery, *, lease_seconds: float) -> bool:
        script = """
        local started = redis.call('HGET', KEYS[1], ARGV[1])
        if (not started) or (tonumber(ARGV[2]) - tonumber(started) >= tonumber(ARGV[3])) then
            redis.call('HSET', KEYS[1], ARGV[1], ARGV[2])
            return 1
        end
        return 0
        """
        claimed = self.client.eval(script, 1, self.started, delivery.delivery_id, str(time.time()), str(lease_seconds))
        return bool(claimed)

    def requeue(self, delivery: Delivery) -> None:
        if delivery.raw:
            self.client.lrem(self.processing, 1, delivery.raw)
            self.client.lpush(self.ready, delivery.raw)
        self.client.hdel(self.started, delivery.delivery_id)

    def discard(self, delivery: Delivery) -> None:
        self.ack(delivery)

    def pending_count(self) -> int:
        return int(self.client.llen(self.ready)) + int(self.client.llen(self.processing))

    def sizes(self) -> dict[str, int]:
        return {
            "ready": int(self.client.llen(self.ready)),
            "processing": int(self.client.llen(self.processing)),
            "started_entries": int(self.client.hlen(self.started)),
        }

    def memory(self) -> dict[str, Any]:
        info = self.client.info("memory")
        return {
            "used_memory_bytes": int(info.get("used_memory", 0)),
            "used_memory_human": str(info.get("used_memory_human", "")),
        }

    def depth(self) -> int:
        return int(self.client.llen(self.ready))

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass


class StreamsAdapter(BaseAdapter):
    """Redis Streams consumer group with XACK/XAUTOCLAIM experiment path."""

    scheme = "streams"

    def __init__(self, url: str, *, run_id: str, consumer: str | None = None) -> None:
        import redis

        self.client = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=1, socket_timeout=3)
        self.client.ping()
        self.stream = f"{QUEUE_PREFIX}:streams:{run_id}"
        self.group = f"{QUEUE_PREFIX}:streams:{run_id}:group"
        self.consumer = consumer or f"consumer-{uuid.uuid4().hex[:10]}"
        try:
            self.client.xgroup_create(self.stream, self.group, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def publish(self, job_id: int) -> Delivery:
        delivery_id = f"streams-{uuid.uuid4().hex}"
        message_id = self.client.xadd(
            self.stream,
            {"job_id": str(job_id), "delivery_id": delivery_id},
            maxlen=10000,
            approximate=True,
        )
        return Delivery(self.scheme, job_id, delivery_id, message_id=str(message_id))

    @staticmethod
    def _delivery(fields: dict[str, Any], message_id: str) -> Delivery:
        return Delivery(
            "streams",
            int(fields["job_id"]),
            str(fields.get("delivery_id") or message_id),
            message_id=message_id,
        )

    def consume_one(self, timeout: int = 1) -> Delivery | None:
        rows = self.client.xreadgroup(
            self.group,
            self.consumer,
            {self.stream: ">"},
            count=1,
            block=max(1, timeout) * 1000,
        )
        if not rows:
            return None
        _stream, messages = rows[0]
        if not messages:
            return None
        message_id, fields = messages[0]
        return self._delivery(fields, message_id)

    def ack(self, delivery: Delivery) -> None:
        if delivery.message_id:
            self.client.xack(self.stream, self.group, delivery.message_id)

    def stale(self, *, lease_seconds: float) -> list[Delivery]:
        min_idle_ms = max(1, int(lease_seconds * 1000))
        try:
            _next_id, messages, _deleted = self.client.xautoclaim(
                self.stream,
                self.group,
                self.consumer,
                min_idle_time=min_idle_ms,
                start_id="0-0",
                count=20,
            )
            return [self._delivery(fields, message_id) for message_id, fields in messages]
        except Exception:
            # Older redis-py fallback: inspect PEL then XCLAIM.
            pending = self.client.xpending_range(self.stream, self.group, "-", "+", 20)
            stale_ids = [item["message_id"] for item in pending if item.get("time") and item["time"] >= min_idle_ms]
            if not stale_ids:
                return []
            rows = self.client.xclaim(
                self.stream,
                self.group,
                self.consumer,
                min_idle_time=min_idle_ms,
                message_ids=stale_ids,
            )
            return [self._delivery(fields, message_id) for message_id, fields in rows]

    def requeue(self, delivery: Delivery) -> None:
        # The PEL entry is already owned by this consumer; re-publishing would
        # create a second stream entry. Leave it for the worker to process.
        return None

    def discard(self, delivery: Delivery) -> None:
        self.ack(delivery)

    def pending_count(self) -> int:
        summary = self.client.xpending(self.stream, self.group)
        if isinstance(summary, dict):
            return int(summary.get("pending", 0))
        return int(summary or 0)

    def sizes(self) -> dict[str, int]:
        return {
            "stream_length": int(self.client.xlen(self.stream)),
            "pending_entries": self.pending_count(),
        }

    def memory(self) -> dict[str, Any]:
        info = self.client.info("memory")
        return {
            "used_memory_bytes": int(info.get("used_memory", 0)),
            "used_memory_human": str(info.get("used_memory_human", "")),
        }

    def depth(self) -> int:
        return int(self.client.xlen(self.stream))

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass


def make_adapter(scheme: str, url: str, *, run_id: str, consumer: str | None = None) -> BaseAdapter:
    if scheme == "list":
        return ListOutboxAdapter(url, run_id=run_id)
    if scheme == "blmove":
        return BLMOVEAdapter(url, run_id=run_id)
    if scheme == "streams":
        return StreamsAdapter(url, run_id=run_id, consumer=consumer)
    raise ValueError(f"unknown scheme: {scheme}")
