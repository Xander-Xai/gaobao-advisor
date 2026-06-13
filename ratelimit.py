"""
限流模块 — 纯标准库实现的令牌桶。
用于 gaobao-advisor 防止 API 滥用。
"""
import threading
import time


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


class RateLimiter:
    """多层限流协调器：IP 小时配额 + 日配额 + 输入长度校验。

    数据结构: {key: {"hourly": TokenBucket, "daily": TokenBucket, "date": str}}
    每天零点重置日桶（通过记录日期实现）。
    通过 LRU 策略防止 _buckets 无界增长导致内存泄漏。
    """

    MAX_KEYS_DEFAULT = 10000  # 默认 LRU 上限

    def __init__(self, hourly_limit: int = 20, daily_limit: int = 40,
                 max_input_len: int = 500, max_keys: int | None = None):
        self.hourly_limit = hourly_limit
        self.daily_limit = daily_limit
        self.max_input_len = max_input_len
        self.max_keys = max_keys if max_keys is not None else self.MAX_KEYS_DEFAULT
        self._buckets: dict = {}
        self._key_order: dict = {}  # key -> last_access_counter (LRU 顺序)
        self._access_counter = 0
        self._lock = threading.Lock()

    def _get_buckets(self, key: str):
        """获取或创建某个 key 的桶组。线程安全。

        每次访问都会更新 LRU 时间戳；超过 max_keys 时按最久未访问顺序批量淘汰 10%。
        """
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = {
                    "hourly": TokenBucket(
                        capacity=self.hourly_limit,
                        refill_rate=self.hourly_limit / 3600.0  # 均匀补充
                    ),
                    "daily": TokenBucket(
                        capacity=self.daily_limit,
                        refill_rate=self.daily_limit / 86400.0
                    ),
                    "date": time.strftime("%Y-%m-%d"),
                }
            entry = self._buckets[key]
            # 跨天重置日桶
            today = time.strftime("%Y-%m-%d")
            if entry["date"] != today:
                entry["daily"] = TokenBucket(
                    capacity=self.daily_limit,
                    refill_rate=self.daily_limit / 86400.0
                )
                entry["date"] = today
            # 记录 LRU 访问时间戳
            self._access_counter += 1
            self._key_order[key] = self._access_counter
            # 超过上限时淘汰最久未访问的 10%（分摊成本）
            if len(self._buckets) > self.max_keys:
                evict_count = max(1, self.max_keys // 10)
                sorted_keys = sorted(self._key_order.items(), key=lambda x: x[1])
                for old_key, _ in sorted_keys[:evict_count]:
                    self._buckets.pop(old_key, None)
                    self._key_order.pop(old_key, None)
            return entry

    def check(self, key: str, msg_length: int = 0) -> tuple:
        """检查请求是否被允许。

        Returns:
            (True, "ok")            — 允许
            (False, "hourly_limit") — 小时配额超限
            (False, "daily_limit")  — 日配额超限
            (False, "input_too_long") — 输入超长
        """
        if self.max_input_len and msg_length > self.max_input_len:
            return (False, "input_too_long")
        entry = self._get_buckets(key)
        if not entry["hourly"].allow():
            return (False, "hourly_limit")
        if not entry["daily"].allow():
            return (False, "daily_limit")
        return (True, "ok")
