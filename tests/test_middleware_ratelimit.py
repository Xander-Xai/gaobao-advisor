"""Tests for rate limit middleware."""

import time

from server.middleware.ratelimit import TokenBucketLimiter


def test_allows_requests_under_limit():
    limiter = TokenBucketLimiter(rate=10, capacity=10)
    for _ in range(10):
        assert limiter.allow("192.168.1.1") is True


def test_blocks_requests_over_limit():
    limiter = TokenBucketLimiter(rate=1, capacity=3)
    for _ in range(3):
        assert limiter.allow("10.0.0.1") is True
    assert limiter.allow("10.0.0.1") is False


def test_different_ips_independent():
    limiter = TokenBucketLimiter(rate=1, capacity=1)
    assert limiter.allow("1.1.1.1") is True
    assert limiter.allow("2.2.2.2") is True
    assert limiter.allow("1.1.1.1") is False


def test_token_refill():
    limiter = TokenBucketLimiter(rate=100, capacity=2)
    limiter.allow("test")
    limiter.allow("test")
    assert limiter.allow("test") is False
    time.sleep(0.05)
    assert limiter.allow("test") is True
