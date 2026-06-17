"""
Comprehensive tests for server.services.rag_cache module.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from server.services.rag_cache import CacheEntry, RagCache, get_rag_cache


class TestCacheEntry:
    """CacheEntry dataclass creation and defaults."""

    def test_default_hit_type(self):
        entry = CacheEntry(
            query_hash="abc123",
            user_msg="hello",
            slots_json="{}",
            result_json='{"key": "val"}',
            timestamp=100.0,
            ttl=3600,
        )
        assert entry.hit_type == "exact"

    def test_custom_hit_type(self):
        entry = CacheEntry(
            query_hash="abc123",
            user_msg="hello",
            slots_json="{}",
            result_json='{"key": "val"}',
            timestamp=100.0,
            ttl=3600,
            hit_type="semantic",
        )
        assert entry.hit_type == "semantic"

    def test_all_fields_stored(self):
        entry = CacheEntry(
            query_hash="abc",
            user_msg="test",
            slots_json='{"province": "广东"}',
            result_json='{"a": 1}',
            timestamp=200.0,
            ttl=86400,
        )
        assert entry.query_hash == "abc"
        assert entry.user_msg == "test"
        assert entry.ttl == 86400


class TestComputeHash:
    """_compute_query_hash behavior."""

    def test_deterministic(self):
        cache = RagCache(redis_url=None)
        h1 = cache._compute_query_hash("  Hello  World  ", {"key": "val"})
        h2 = cache._compute_query_hash("Hello World", {"key": "val"})
        assert h1 == h2

    def test_different_queries_different_hashes(self):
        cache = RagCache(redis_url=None)
        h1 = cache._compute_query_hash("hello", {"a": "1"})
        h2 = cache._compute_query_hash("world", {"a": "1"})
        assert h1 != h2

    def test_different_slots_different_hashes(self):
        cache = RagCache(redis_url=None)
        h1 = cache._compute_query_hash("hello", {"province": "广东"})
        h2 = cache._compute_query_hash("hello", {"province": "山东"})
        assert h1 != h2

    def test_slot_key_order_independent(self):
        cache = RagCache(redis_url=None)
        h1 = cache._compute_query_hash("test", {"b": "2", "a": "1"})
        h2 = cache._compute_query_hash("test", {"a": "1", "b": "2"})
        assert h1 == h2

    def test_empty_slots_excluded(self):
        cache = RagCache(redis_url=None)
        h1 = cache._compute_query_hash("hello", {})
        h2 = cache._compute_query_hash("hello", {"empty_str": ""})
        # Empty string slots should be filtered out
        assert h1 == h2

    def test_whitespace_normalized(self):
        cache = RagCache(redis_url=None)
        h1 = cache._compute_query_hash("  Hello   World!\n", {"a": "1"})
        h2 = cache._compute_query_hash("hello world!", {"a": "1"})
        assert h1 == h2


class TestMemoryCache:
    """Tests that exercise only the in-memory cache (no Redis)."""

    @pytest.fixture(autouse=True)
    def disable_redis(self):
        with patch("server.services.rag_cache.REDIS_AVAILABLE", False):
            yield

    @pytest.fixture
    def cache(self):
        return RagCache(redis_url=None, max_memory_entries=5, exact_ttl=86400, semantic_ttl=3600)

    def test_get_returns_none_for_miss(self, cache):
        result = cache.get("nonexistent", {})
        assert result is None

    def test_set_and_get_exact(self, cache):
        result = {"schools": ["清华", "北大"], "quotes": []}
        cache.set("hello", {"province": "北京"}, result, hit_type="exact")
        cached = cache.get("hello", {"province": "北京"})
        assert cached == result

    def test_set_and_get_semantic(self, cache):
        result = {"schools": ["浙大"]}
        cache.set("hello", {}, result, hit_type="semantic")
        cached = cache.get("hello", {})
        assert cached == result

    def test_get_returns_none_after_expiry(self, cache):
        """Test that expired entries return None."""
        cache.set("hello", {}, {"data": "test"}, hit_type="exact")

        # Overwrite with a past expiry to simulate expiration
        query_hash = cache._compute_query_hash("hello", {})
        cache._memory_cache[query_hash] = ({"data": "test"}, 0.0)  # expiry at epoch → definitely expired

        # get should return None since expiry is in the past
        result = cache.get("hello", {})
        assert result is None

        # Verify the entry was removed from cache
        assert query_hash not in cache._memory_cache

    def test_set_overwrites_existing_key(self, cache):
        cache.set("k", {}, {"v": 1})
        cache.set("k", {}, {"v": 2})
        assert cache.get("k", {}) == {"v": 2}

    def test_lru_eviction_oldest_removed(self, cache):
        """When over max_memory_entries, oldest entry should be evicted."""
        # Fill cache to max
        for i in range(5):
            cache.set(f"key{i}", {}, {"data": i}, hit_type="exact")

        # Verify all present
        for i in range(5):
            assert cache.get(f"key{i}", {}) == {"data": i}

        # Insert one more — should evict oldest (key0)
        cache.set("key5", {}, {"data": 5}, hit_type="exact")

        # key0 should be evicted; others should remain
        assert cache.get("key0", {}) is None
        assert cache.get("key1", {}) == {"data": 1}
        assert cache.get("key5", {}) == {"data": 5}

    def test_expired_entries_removed_before_eviction(self, cache):
        """Eviction should clean expired entries first before removing oldest."""
        cache.set("fresh", {}, {"data": "fresh"}, hit_type="exact")
        cache.set("stale", {}, {"data": "stale"}, hit_type="semantic")

        # Manually expire the "stale" entry
        stale_hash = cache._compute_query_hash("stale", {})
        cache._memory_cache[stale_hash] = ({"data": "stale"}, 0.0)

        # Fill cache to capacity so eviction triggers
        for i in range(4):
            cache.set(f"key{i}", {}, {"data": i}, hit_type="exact")

        # "stale" should have been cleaned up during eviction
        assert cache.get("stale", {}) is None
        # "fresh" should survive since it's not expired
        assert cache.get("fresh", {}) == {"data": "fresh"}

    def test_serialization_failure_does_not_store(self, cache):
        """set() should silently skip when result can't be serialized."""
        d = {}
        d["self"] = d  # Circular reference raises ValueError

        with patch("server.services.rag_cache.logger") as mock_log:
            cache.set("bad", {}, d)
            mock_log.warning.assert_called_once()
            assert cache.get("bad", {}) is None

    def test_clear_removes_all_memory_entries(self, cache):
        cache.set("a", {}, {"v": 1})
        cache.set("b", {}, {"v": 2})
        cache.clear()
        assert cache.get("a", {}) is None
        assert cache.get("b", {}) is None
        assert len(cache._memory_cache) == 0

    def test_get_stats_without_redis(self, cache):
        stats = cache.get_stats()
        assert stats["memory_entries"] == 0
        assert stats["memory_max"] == 5
        assert stats["redis_connected"] is False


class TestRedisCache:
    """Tests that exercise Redis cache with a mocked Redis client."""

    @pytest.fixture
    def mock_redis(self):
        return MagicMock()

    @pytest.fixture
    def cache(self, mock_redis):
        with (
            patch("server.services.rag_cache._Redis", create=True),
            patch("server.services.rag_cache.REDIS_AVAILABLE", True),
        ):
            cache = RagCache(redis_url="redis://localhost:6379/0", max_memory_entries=10)
            cache._redis = mock_redis
            return cache

    def test_get_redis_hit(self, cache, mock_redis):
        mock_redis.get.return_value = json.dumps({"schools": ["THU"]})
        result = cache.get("hello", {})
        assert result == {"schools": ["THU"]}
        mock_redis.get.assert_called_once()

    def test_get_redis_miss_falls_back_to_memory(self, cache, mock_redis):
        mock_redis.get.return_value = None
        cache.set("hello", {}, {"from": "memory"})
        result = cache.get("hello", {})
        assert result == {"from": "memory"}

    def test_set_stores_to_redis(self, cache, mock_redis):
        result = {"data": "test"}
        cache.set("hello", {"province": "北京"}, result)
        mock_redis.setex.assert_called_once()
        args, _ = mock_redis.setex.call_args
        key, ttl, value = args
        assert key.startswith("rag:")
        assert ttl == 86400  # exact_ttl
        assert json.loads(value) == result

    def test_set_semantic_uses_shorter_ttl(self, cache, mock_redis):
        result = {"data": "semantic"}
        cache.set("hello", {}, result, hit_type="semantic")
        args, _ = mock_redis.setex.call_args
        _, ttl, _ = args
        assert ttl == 3600

    def test_redis_failure_falls_back_to_memory(self, cache, mock_redis):
        mock_redis.get.side_effect = Exception("Connection refused")
        cache.set("hello", {}, {"data": "memory"})
        # get should log warning and fall through to memory
        result = cache.get("hello", {})
        assert result == {"data": "memory"}

    def test_clear_redis_and_memory(self, cache, mock_redis):
        mock_redis.keys.return_value = ["rag:hash1", "rag:hash2"]
        cache.set("a", {}, {"v": 1})
        cache.set("b", {}, {"v": 2})
        cache.clear()
        assert cache.get("a", {}) is None
        assert cache.get("b", {}) is None
        mock_redis.delete.assert_called_once_with("rag:hash1", "rag:hash2")

    def test_clear_redis_no_keys(self, cache, mock_redis):
        mock_redis.keys.return_value = []
        cache.clear()
        mock_redis.delete.assert_not_called()

    def test_clear_redis_error(self, cache, mock_redis):
        mock_redis.keys.side_effect = Exception("Redis error")
        with patch("server.services.rag_cache.logger") as mock_log:
            cache.clear()
            mock_log.warning.assert_called()

    def test_redis_connection_failure_uses_memory(self):
        """When Redis connection fails, RagCache falls back to memory."""
        with (
            patch("server.services.rag_cache.REDIS_AVAILABLE", True),
            patch("redis.from_url") as mock_from_url,
        ):
            mock_from_url.side_effect = Exception("Connection refused")
            cache = RagCache(redis_url="redis://localhost:6379/0")
            assert cache._redis is None
            cache.set("hello", {}, {"fallback": True})
            assert cache.get("hello", {}) == {"fallback": True}


class TestGetRagCache:
    """Singleton accessor function."""

    def teardown_method(self):
        # Reset the singleton after each test
        from server.services import rag_cache

        rag_cache._cache = None

    def test_returns_rag_cache_instance(self):
        cache = get_rag_cache(redis_url=None)
        assert isinstance(cache, RagCache)

    def test_singleton(self):
        cache1 = get_rag_cache(redis_url=None)
        cache2 = get_rag_cache(redis_url=None)
        assert cache1 is cache2

    def test_custom_max_entries_on_first_call(self):
        cache = get_rag_cache(redis_url=None, max_memory_entries=500)
        assert cache._max_memory_entries == 500


class TestEdgeCases:
    """Edge cases for the cache system."""

    @pytest.fixture(autouse=True)
    def disable_redis_except_where_needed(self, request):
        if "redis" not in request.node.name:
            with patch("server.services.rag_cache.REDIS_AVAILABLE", False):
                yield
        else:
            yield

    def test_unicode_text(self):
        cache = RagCache(redis_url=None)
        cache.set("你好世界", {"province": "广东"}, {"msg": "测试"})
        result = cache.get("你好世界", {"province": "广东"})
        assert result == {"msg": "测试"}

    def test_normalized_unicode_match(self):
        cache = RagCache(redis_url=None)
        cache.set(" 你好  世界 ", {"province": "广东"}, {"msg": "matched"})
        result = cache.get("你好 世界", {"province": "广东"})
        assert result == {"msg": "matched"}

    def test_get_empty_string_query(self):
        cache = RagCache(redis_url=None)
        assert cache.get("", {}) is None

    def test_clear_empty_cache(self):
        cache = RagCache(redis_url=None)
        cache.clear()
        assert cache.get("a", {}) is None
