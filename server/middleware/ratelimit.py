"""Token bucket rate limiter for FastAPI with TTL eviction."""
import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# Evict entries idle longer than this (seconds)
_MAX_IDLE_SECONDS = 3600  # 1 hour
# Run eviction check every N requests
_EVICTION_INTERVAL = 500


class TokenBucketLimiter:
    """Per-IP token bucket rate limiter with TTL-based eviction."""

    def __init__(self, rate: float = 20, capacity: int = 40):
        self.rate = rate
        self.capacity = capacity
        self._buckets: dict[str, tuple[float, float]] = {}
        self._request_count: int = 0

    def allow(self, ip: str) -> bool:
        now = time.monotonic()

        # Periodic eviction of idle entries
        self._request_count += 1
        if self._request_count % _EVICTION_INTERVAL == 0:
            self._evict_idle(now)

        if ip not in self._buckets:
            self._buckets[ip] = (self.capacity, now)
        tokens, last = self._buckets[ip]
        elapsed = now - last
        tokens = min(self.capacity, tokens + elapsed * self.rate)
        if tokens < 1:
            return False
        self._buckets[ip] = (tokens - 1, now)
        return True

    def _evict_idle(self, now: float) -> None:
        """Remove entries that have been idle (fully refilled) for too long."""
        idle_ips = [
            ip for ip, (tokens, last) in self._buckets.items()
            if now - last > _MAX_IDLE_SECONDS and tokens >= self.capacity
        ]
        for ip in idle_ips:
            del self._buckets[ip]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware enforcing token bucket rate limits per IP."""

    def __init__(self, app, rate: float = 20, capacity: int = 40):
        super().__init__(app)
        self.limiter = TokenBucketLimiter(rate=rate, capacity=capacity)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        if not self.limiter.allow(client_ip):
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
        return await call_next(request)
