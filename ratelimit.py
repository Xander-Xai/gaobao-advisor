"""
限流模块 — 纯标准库实现的令牌桶。
用于 xuefeng-advisor 防止 API 滥用。
"""
import time
import threading


class TokenBucket:
    """单桶令牌桶：capacity 个令牌，按 refill_rate 个/秒补充。"""

    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: 桶容量（最大突发请求数）
            refill_rate: 令牌补充速率（个/秒）
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self):
        """惰性补充：根据流逝时间增加令牌。"""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def allow(self, cost: float = 1.0) -> bool:
        """尝试消费一个令牌。成功返回 True，失败返回 False。"""
        with self._lock:
            self._refill()
            if self.tokens >= cost:
                self.tokens -= cost
                return True
            return False
