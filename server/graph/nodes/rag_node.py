"""RAG retrieval node.

Behaviour (honest by construction):

* When the corpus is available, retrieval returns real chunks plus citations.
  Those citations are written to ``rag_sources`` and embedded into
  ``knowledge_context`` so the answer can point at its evidence.
* When the corpus is missing, corrupt or retrieval fails, the node records an
  explicit ``RAG_ERROR`` / ``RAG_DISABLED`` state and leaves no knowledge
  context. Downstream rendering and ``/api/v1/health`` surface that value, so a
  broken RAG stack can never be reported as a working one, and the model is
  instructed not to answer as if it had evidence.
"""

from __future__ import annotations

import logging
from typing import Any

from server.services import rag

logger = logging.getLogger(__name__)


def _last_citations(search_result: dict[str, Any]) -> list[dict[str, Any]]:
    return list(search_result.get("citations", []))


def rag_retrieve_node(state: dict[str, Any]) -> dict[str, Any]:
    """Fetch knowledge chunks and citations, or report why it could not.

    Returns a partial state update. ``rag_state`` is one of ``RAG_ENABLED``,
    ``RAG_DISABLED`` or ``RAG_ERROR``; ``rag_evidence`` is True only when at
    least one chunk was retrieved.
    """
    text = state.get("input_text", "")
    slots = state.get("slots", {})
    trace = list(state.get("trace", []))

    try:
        search_result = rag.search(text, slots)
    except rag.RagDisabledError:
        reason = rag.status()["reason"]
        logger.warning("RAG disabled, skipping retrieval: %s", reason)
        trace.append({"node": "rag_retrieve", "event": "RAG_DISABLED", "reason": reason})
        return {
            "rag_chunks": [],
            "expert_quotes": [],
            "knowledge_context": "",
            "rag_state": "RAG_DISABLED",
            "rag_evidence": False,
            "rag_sources": [],
            "rag_reason": reason,
            "trace": trace,
        }
    except rag.RagError as exc:
        reason = f"{exc.__class__.__name__}: {exc}"
        logger.error("RAG unavailable: %s", reason)
        trace.append({"node": "rag_retrieve", "event": "RAG_ERROR", "reason": reason})
        return {
            "rag_chunks": [],
            "expert_quotes": [],
            "knowledge_context": "",
            "rag_state": "RAG_ERROR",
            "rag_evidence": False,
            "rag_sources": [],
            "rag_reason": reason,
            "trace": trace,
        }
    except Exception as exc:  # noqa: BLE001 - unexpected failure is still fail-closed
        reason = f"retrieval error: {exc.__class__.__name__}"
        logger.exception("RAG retrieval failed")
        trace.append({"node": "rag_retrieve", "event": "RAG_ERROR", "reason": reason})
        return {
            "rag_chunks": [],
            "expert_quotes": [],
            "knowledge_context": "",
            "rag_state": "RAG_ERROR",
            "rag_evidence": False,
            "rag_sources": [],
            "rag_reason": reason,
            "trace": trace,
        }

    rag_chunks: list[dict] = search_result.get("group_chunks", [])
    expert_quotes: list[dict] = search_result.get("quotes", [])
    citations = _last_citations(search_result)
    has_evidence = bool(search_result.get("has_evidence")) and bool(rag_chunks)

    if has_evidence:
        parts = []
        for chunk in rag_chunks:
            source = chunk.get("source") or chunk.get("section_title") or chunk.get("group_id", "")
            content = chunk.get("text", "")
            parts.append(f"[来源: {source}]\n{content}")
        knowledge_context = "\n\n".join(parts)
    else:
        knowledge_context = ""

    trace.append(
        {
            "node": "rag_retrieve",
            "event": f"chunks={len(rag_chunks)},quotes={len(expert_quotes)},has_evidence={has_evidence}",
        }
    )

    return {
        "rag_chunks": rag_chunks,
        "expert_quotes": expert_quotes,
        "knowledge_context": knowledge_context,
        "rag_state": "RAG_ENABLED",
        "rag_evidence": has_evidence,
        "rag_sources": citations if has_evidence else [],
        "rag_reason": "" if has_evidence else "corpus is available but holds no matching evidence",
        "trace": trace,
    }
