"""
RAG (Retrieval-Augmented Generation) service wrapper.

Thin wrapper around kb_retriever.KbRetriever and quality.knowledge_loader
that exposes a clean interface for the server layer with lazy initialization.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

from server.services.rag_cache import RagCache

logger = logging.getLogger(__name__)

_retriever = None
_groups_dir: str = ""
_quotes_path: str = ""
_active_provider: str = "unknown"
_cache = RagCache()


class RagDisabledError(RuntimeError):
    """Raised when RAG retrieval is requested but no corpus is available.

    The public demo ships without a knowledge corpus (the upstream corpus has
    no clear redistribution rights). Retrieval therefore fails loudly instead
    of returning an empty result that downstream code would mistake for
    "nothing relevant found".
    """


def status() -> dict[str, Any]:
    """Report whether RAG is usable, and why not if it is not.

    Downstream code (notably ``/api/v1/health``) surfaces this so that a
    disabled RAG stack can never be reported as a healthy system.
    """
    configured = bool(_groups_dir) and bool(_quotes_path)
    groups_dir_exists = bool(_groups_dir) and os.path.isdir(_groups_dir)
    enabled_env = os.getenv("ENABLE_RAG_KB", "").lower() in ("true", "1", "yes")

    if not enabled_env:
        state, reason = "RAG_DISABLED", "ENABLE_RAG_KB is not enabled"
    elif not configured:
        state, reason = "RAG_DISABLED", "RAG corpus was never configured (configure() not called)"
    elif not groups_dir_exists:
        state, reason = "RAG_DISABLED", f"configured corpus directory is absent: {_groups_dir}"
    else:
        state, reason = "RAG_ENABLED", ""

    return {
        "state": state,
        "reason": reason,
        "corpus_configured": configured,
        "provider": _active_provider,
    }


def is_available() -> bool:
    """True only when retrieval can actually return evidence."""
    return status()["state"] == "RAG_ENABLED"


def configure(groups_dir: str, quotes_path: str) -> None:
    """Set paths for the RAG knowledge base. Call before first use.

    Embedding provider is selected from env var RAG_EMBEDDING_PROVIDER
    (siliconflow | openai | dashscope | ollama | keyword). Defaults to
    siliconflow if SILICONFLOW_API_KEY is set, otherwise keyword.

    Raises:
        RagDisabledError: if ``ENABLE_RAG_KB`` is not enabled. Configuring a
            corpus the deployment will not use would re-introduce the
            silent-degradation class of bug this module guards against.
    """
    if os.getenv("ENABLE_RAG_KB", "").lower() not in ("true", "1", "yes"):
        raise RagDisabledError("cannot configure a RAG corpus while ENABLE_RAG_KB is not enabled")

    global _groups_dir, _quotes_path, _active_provider
    _groups_dir = groups_dir
    _quotes_path = quotes_path
    _active_provider = os.getenv("RAG_EMBEDDING_PROVIDER", "").lower() or _default_provider()
    logger.info("RAG configured: groups_dir=%s, provider=%s", groups_dir, _active_provider)


def _default_provider() -> str:
    """Pick a default provider based on which API key is available."""
    if os.getenv("SILICONFLOW_API_KEY"):
        return "siliconflow"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("DASHSCOPE_API_KEY"):
        return "dashscope"
    return "keyword"


def _get_retriever():
    """Lazy-init the KbRetriever singleton with the configured provider."""
    global _retriever
    if _retriever is None:
        from server.services.kb_retriever import KbRetriever, create_embedding_provider

        provider_name = _active_provider if _active_provider != "unknown" else _default_provider()
        embedder = create_embedding_provider(provider_name)
        _retriever = KbRetriever(
            groups_dir=_groups_dir,
            quotes_path=_quotes_path,
            embedding_provider=embedder,
        )
        logger.info(
            "KbRetriever initialized: provider=%s, groups=%d, quotes=%d",
            provider_name,
            len(_retriever._groups),
            len(_retriever._quotes),
        )
    return _retriever


def _make_cache_key(user_msg: str, slots: dict) -> str:
    """Build a deterministic cache key from the query and slots."""
    normalized = user_msg.strip().lower()
    return hashlib.md5(f"{normalized}|{json.dumps(slots, sort_keys=True)}".encode()).hexdigest()


def search(user_msg: str, slots: dict | None = None) -> dict[str, Any]:
    """Search the knowledge base for relevant content.

    Results are cached by (user_msg, slots) to avoid redundant retrievals.

    Returns:
        dict with keys: groups, group_chunks, quotes
    """
    from server.metrics import record_cache_hit, record_cache_miss

    slots = slots or {}

    if not is_available():
        raise RagDisabledError("RAG retrieval requested but unavailable: " + status()["reason"])

    # Check cache first
    cached = _cache.get(user_msg, slots)
    if cached is not None:
        record_cache_hit()
        return cached

    record_cache_miss()

    result = _get_retriever().search(user_msg, slots)
    response = {
        "groups": result.groups,
        "group_chunks": [
            {
                "text": c.text,
                "group_id": c.group_id,
                "section_title": c.section_title,
                "start_line": c.start_line,
            }
            for c in result.group_chunks
        ],
        "quotes": [
            {
                "id": q.id,
                "text": q.text,
                "major": q.major,
                "tags": q.tags,
                "category": q.category,
                "sentiment": q.sentiment,
                "source": q.source,
                "year": q.year,
            }
            for q in result.quotes
        ],
    }

    # Write to cache
    _cache.set(user_msg, slots, response)
    return response


def load_contextual_knowledge(
    user_msg: str,
    slots: dict | None = None,
    max_files: int = 2,
) -> str | None:
    """Load contextual knowledge using the quality knowledge_loader.

    Falls back to keyword-based loading when RAG is not configured.
    """
    from quality.knowledge_loader import load_contextual_knowledge as _load

    retriever = None
    if _retriever is not None:
        retriever = _retriever
    return _load(user_msg, slots, max_files, kb_retriever=retriever)
