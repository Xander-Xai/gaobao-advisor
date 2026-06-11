"""限流器单元测试 — 先写测试，验证行为，再实现。"""
import time
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ratelimit import TokenBucket

def test_token_bucket_initial_allow():
    """新桶首次请求应该被允许。"""
    bucket = TokenBucket(capacity=5, refill_rate=1.0)
    assert bucket.allow() is True


def test_token_bucket_exhaustion():
    """桶耗尽后应拒绝请求。"""
    bucket = TokenBucket(capacity=3, refill_rate=0.001)  # 极慢补充
    for _ in range(3):
        assert bucket.allow() is True
    assert bucket.allow() is False


def test_token_bucket_refill():
    """等待补充后应允许新请求。"""
    bucket = TokenBucket(capacity=2, refill_rate=100.0)  # 100 token/秒
    for _ in range(2):
        bucket.allow()
    time.sleep(0.05)  # 等待 50ms，应补充约 5 个 token
    assert bucket.allow() is True


from ratelimit import RateLimiter


def test_rate_limiter_separates_keys():
    """不同 key（IP）应有独立配额。"""
    limiter = RateLimiter(hourly_limit=2, daily_limit=5)
    assert limiter.check("ip_A") is True
    assert limiter.check("ip_A") is True
    assert limiter.check("ip_B") is True  # 另一个 IP 不受影响


def test_rate_limiter_hourly_quota():
    """超出小时配额应返回 False。"""
    limiter = RateLimiter(hourly_limit=3, daily_limit=100)
    for _ in range(3):
        assert limiter.check("ip_X") is True
    assert limiter.check("ip_X") is False


def test_rate_limiter_daily_quota():
    """小时配额通过但日配额超限，仍应返回 False。"""
    # 小时设大、日设小，便于测日配额
    limiter = RateLimiter(hourly_limit=100, daily_limit=2)
    assert limiter.check("ip_Y") is True
    assert limiter.check("ip_Y") is True
    assert limiter.check("ip_Y") is False


def test_rate_limiter_input_length_check():
    """输入超长应返回 False（input_too_long 标记）。"""
    limiter = RateLimiter(hourly_limit=10, daily_limit=10, max_input_len=100)
    result = limiter.check("ip_Z", msg_length=200)
    assert result == "input_too_long"
    assert limiter.check("ip_Z", msg_length=50) is True  # 正常长度仍可用
