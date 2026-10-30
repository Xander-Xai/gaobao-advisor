"""In-process sliding-window limiter for sensitive admin endpoints.

The global rate-limit middleware protects the public API; this adds a tighter,
keyed limit for login and job writes. It is intentionally process-local: a
multi-worker deployment should move the counter to Redis. That trade-off is
documented in the ADR instead of pretending it is distributed.
"""

from __future__ import annotations

import threading
import time
from collections import deque


class SlidingWindowLimiter:
    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Return ``(allowed, retry_after_seconds)`` and record the hit."""
        now = time.monotonic()
        with self._lock:
            bucket = self._hits.setdefault(key, deque())
            cutoff = now - self.window
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                retry_after = max(1, int(self.window - (now - bucket[0])) + 1)
                return False, retry_after
            bucket.append(now)
            if len(self._hits) > 10_000:
                self._hits = {k: v for k, v in self._hits.items() if v and v[-1] >= cutoff}
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
