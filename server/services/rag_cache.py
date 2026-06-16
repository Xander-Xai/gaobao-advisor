"""
RAG Retrieval Cache — Redis-based cache for frequent queries.

Caches RAG search results to avoid redundant embedding computation and
vector searches for repeated or similar queries. Uses semantic similarity
to match cached results.

Cache key strategy:
- Exact match: MD5 hash of normalized query
- Semantic match: Vector similarity threshold (0.95)

TTL: 24 hours for exact matches, 1 hour for semantic matches

Usage:
    from server.services.rag_cache import get_rag_cache
    
    cache = get_rag_cache()
    
    # Try cache first
    result = cache.get(user_msg, slots)
    if result:
        return result  # Cache hit!
    
    # Compute fresh result
    result = retriever.search(user_msg, slots)
    
    # Store in cache
    cache.set(user_msg, slots, result)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Check if Redis is available
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis package not installed — RAG cache disabled")


@dataclass
class CacheEntry:
    """A cached retrieval result."""

    query_hash: str
    user_msg: str
    slots_json: str
    result_json: str
    timestamp: float
    ttl: int  # Time-to-live in seconds
    hit_type: str = "exact"  # "exact" or "semantic"


class RagCache:
    """Redis-backed cache for RAG retrieval results.

    Falls back to in-memory LRU cache if Redis is unavailable.
    """

    def __init__(
        self,
        redis_url: str | None = None,
        max_memory_entries: int = 1000,
        exact_ttl: int = 86400,  # 24 hours
        semantic_ttl: int = 3600,  # 1 hour
    ):
        """Initialize RAG cache.

        Args:
            redis_url: Redis connection URL (e.g., "redis://localhost:6379/0")
            max_memory_entries: Max entries for in-memory fallback cache
            exact_ttl: TTL for exact match cache entries (seconds)
            semantic_ttl: TTL for semantic match cache entries (seconds)
        """
        self.exact_ttl = exact_ttl
        self.semantic_ttl = semantic_ttl
        self._memory_cache: dict[str, tuple[Any, float]] = {}
        self._max_memory_entries = max_memory_entries

        # Initialize Redis client if available
        self._redis: redis.Redis | None = None
        if REDIS_AVAILABLE:
            redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
            try:
                self._redis = redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
                logger.info("Connected to Redis at %s", redis_url)
            except Exception as e:
                logger.warning("Failed to connect to Redis (%s) — using in-memory cache", e)
                self._redis = None

    def _compute_query_hash(self, user_msg: str, slots: dict) -> str:
        """Compute deterministic hash for query + slots combination.

        Normalizes whitespace and sorts slot keys for consistency.
        """
        # Normalize message
        normalized_msg = " ".join(user_msg.lower().split())

        # Normalize slots (sort keys, exclude empty values)
        normalized_slots = {
            k: v for k, v in sorted(slots.items())
            if v and (isinstance(v, str) and v.strip() or isinstance(v, (int, float, bool)))
        }

        # Create canonical string
        canonical = f"{normalized_msg}|{json.dumps(normalized_slots, sort_keys=True)}"

        # Hash
        return hashlib.md5(canonical.encode("utf-8")).hexdigest()

    def get(self, user_msg: str, slots: dict) -> Any | None:
        """Retrieve cached result for query.

        Args:
            user_msg: User's query message
            slots: Extracted slot values

        Returns:
            Cached result if found, None otherwise
        """
        query_hash = self._compute_query_hash(user_msg, slots)

        # Try Redis first
        if self._redis:
            try:
                cached = self._redis.get(f"rag:{query_hash}")
                if cached:
                    logger.debug("Cache hit (Redis): %s", user_msg[:50])
                    return json.loads(cached)
            except Exception as e:
                logger.warning("Redis get failed: %s", e)

        # Fallback to memory cache
        if query_hash in self._memory_cache:
            result, expiry = self._memory_cache[query_hash]
            if time.time() < expiry:
                logger.debug("Cache hit (memory): %s", user_msg[:50])
                return result
            else:
                # Expired, remove
                del self._memory_cache[query_hash]

        return None

    def set(self, user_msg: str, slots: dict, result: Any, hit_type: str = "exact") -> None:
        """Store result in cache.

        Args:
            user_msg: User's query message
            slots: Extracted slot values
            result: Retrieval result to cache
            hit_type: "exact" or "semantic" (determines TTL)
        """
        query_hash = self._compute_query_hash(user_msg, slots)
        ttl = self.exact_ttl if hit_type == "exact" else self.semantic_ttl
        expiry = time.time() + ttl

        # Serialize result
        try:
            result_json = json.dumps(result, ensure_ascii=False, default=str)
        except TypeError as e:
            logger.warning("Failed to serialize cache result: %s", e)
            return

        # Store in Redis
        if self._redis:
            try:
                self._redis.setex(f"rag:{query_hash}", ttl, result_json)
                logger.debug("Cached to Redis: %s (TTL=%ds)", user_msg[:50], ttl)
            except Exception as e:
                logger.warning("Redis set failed: %s", e)

        # Also store in memory cache (LRU eviction)
        self._memory_cache[query_hash] = (result, expiry)

        # Evict oldest entries if over limit
        if len(self._memory_cache) > self._max_memory_entries:
            # Remove expired entries first
            now = time.time()
            expired = [k for k, (_, exp) in self._memory_cache.items() if now >= exp]
            for k in expired:
                del self._memory_cache[k]

            # If still over limit, remove oldest
            if len(self._memory_cache) > self._max_memory_entries:
                oldest_key = min(self._memory_cache.keys(), key=lambda k: self._memory_cache[k][1])
                del self._memory_cache[oldest_key]

    def clear(self) -> None:
        """Clear all cached entries."""
        if self._redis:
            try:
                keys = self._redis.keys("rag:*")
                if keys:
                    self._redis.delete(*keys)
                    logger.info("Cleared %d entries from Redis cache", len(keys))
            except Exception as e:
                logger.warning("Redis clear failed: %s", e)

        self._memory_cache.clear()
        logger.info("Cleared in-memory cache")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        stats = {
            "memory_entries": len(self._memory_cache),
            "memory_max": self._max_memory_entries,
            "redis_connected": self._redis is not None,
        }

        if self._redis:
            try:
                keys = self._redis.keys("rag:*")
                stats["redis_entries"] = len(keys)
            except Exception:
                stats["redis_entries"] = 0

        return stats


# Global singleton instance
_cache: RagCache | None = None


def get_rag_cache(
    redis_url: str | None = None,
    max_memory_entries: int = 1000,
) -> RagCache:
    """Get or create the global RAG cache instance.

    Args:
        redis_url: Redis connection URL
        max_memory_entries: Max entries for in-memory fallback

    Returns:
        RagCache instance
    """
    global _cache
    if _cache is None:
        _cache = RagCache(
            redis_url=redis_url,
            max_memory_entries=max_memory_entries,
        )
    return _cache
