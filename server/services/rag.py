"""
RAG (Retrieval-Augmented Generation) service wrapper.

Thin wrapper around kb_retriever.KbRetriever and quality.knowledge_loader
that exposes a clean interface for the server layer with lazy initialization.
"""

from __future__ import annotations

from typing import Any

_retriever = None
_groups_dir: str = ""
_quotes_path: str = ""


def configure(groups_dir: str, quotes_path: str) -> None:
    """Set paths for the RAG knowledge base. Call before first use."""
    global _groups_dir, _quotes_path
    _groups_dir = groups_dir
    _quotes_path = quotes_path


def _get_retriever():
    """Lazy-init the KbRetriever singleton."""
    global _retriever
    if _retriever is None:
        from kb_retriever import KbRetriever, KeywordOnlyEmbedding
        _retriever = KbRetriever(
            groups_dir=_groups_dir,
            quotes_path=_quotes_path,
            embedding_provider=KeywordOnlyEmbedding(),
        )
    return _retriever


def search(user_msg: str, slots: dict | None = None) -> dict[str, Any]:
    """Search the knowledge base for relevant content.

    Returns:
        dict with keys: groups, group_chunks, quotes
    """
    result = _get_retriever().search(user_msg, slots or {})
    return {
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
            }
            for q in result.quotes
        ],
    }


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
