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
