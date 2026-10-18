"""RAG (Retrieval-Augmented Generation) service wrapper.

Thin wrapper around :class:`server.services.kb_retriever.KbRetriever` that
exposes a clean interface for the server layer.

Default behaviour — *synthetic demo*:

The repository ships an **original, machine-authored, synthetic** knowledge
corpus under ``knowledge/synthetic_demo`` (see that directory's README). In the
default demo environment RAG is therefore *enabled*: the corpus is initialised
automatically on startup and retrieval returns real, citable evidence.

Fail-closed:

Availability is never assumed. If the corpus is missing, fails its integrity
check, or retrieval raises, the service reports an explicit error state and
``search()`` raises rather than returning an empty result that downstream code
could mistake for "nothing relevant found". A caller must never be able to turn
"retrieval is broken" into "answer freely from the model".
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import Any

from server.services.rag_cache import RagCache

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: Root of the corpus bundled with the public demo.
DEFAULT_CORPUS_ROOT = os.path.join(_PROJECT_ROOT, "knowledge", "synthetic_demo")
DEFAULT_GROUPS_DIR = os.path.join(DEFAULT_CORPUS_ROOT, "groups")
DEFAULT_QUOTES_DIR = os.path.join(DEFAULT_CORPUS_ROOT, "quotes")
DEFAULT_MANIFEST_PATH = os.path.join(DEFAULT_CORPUS_ROOT, "manifest.json")

#: Marker every shipped corpus file and the manifest must carry.
CORPUS_MARKER = "SYNTHETIC_DEMO"

_TRUE_VALUES = ("true", "1", "yes", "on")

_retriever = None
_groups_dir: str = ""
_quotes_path: str = ""
_active_provider: str = "unknown"
_configured: bool = False
_config_error: str = ""
_stats: dict[str, Any] = {}
_default_init_attempted: bool = False
_cache = RagCache()


class RagError(RuntimeError):
    """Base class for RAG availability failures."""


class RagDisabledError(RagError):
    """Raised when RAG retrieval is requested but RAG is switched off."""


class RagCorpusError(RagError):
    """Raised when a configured corpus is missing, corrupt or unmarkable.

    This is the fail-closed signal: an operator who removes or damage the demo
    corpus gets a loud error, not a silently evidence-free answer.
    """


class RagUnavailableError(RagError):
    """Raised when a healthy-looking corpus fails at retrieval time."""


def _enabled() -> bool:
    """RAG defaults to on for the synthetic demo; set ENABLE_RAG_KB=false to disable."""
    return os.getenv("ENABLE_RAG_KB", "true").strip().lower() in _TRUE_VALUES


def _default_provider() -> str:
    """Pick a default provider based on which API key is available.

    With no key configured this returns ``keyword``, which needs no network and
    no paid API — the offline demo path.
    """
    if os.getenv("SILICONFLOW_API_KEY"):
        return "siliconflow"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("DASHSCOPE_API_KEY"):
        return "dashscope"
    return "keyword"


def validate_corpus(groups_dir: str, manifest_path: str | None = None) -> tuple[bool, str, dict[str, Any]]:
    """Check that a corpus directory is present, non-empty and self-labelling.

    Returns ``(ok, reason, stats)``. A corpus is accepted only when:

    * the directory exists and contains at least one ``.md`` file;
    * every file is non-empty, carries the ``SYNTHETIC_DEMO`` marker and has at
      least one ``##`` section (so it can actually be chunked);
    * if a manifest is present, it declares the marker and every file it lists
      exists (and matches its recorded sha256 when one is given).

    The synthetic marker is mandatory: this is what stops a non-synthetic (or
    rights-unclear) corpus being silently served as demo knowledge.
    """
    stats: dict[str, Any] = {"documents": 0, "chunks": 0, "marker": "", "manifest": bool(manifest_path)}
    if not groups_dir or not os.path.isdir(groups_dir):
        return False, f"corpus directory is absent: {groups_dir}", stats

    files = sorted(f for f in os.listdir(groups_dir) if f.endswith(".md"))
    if not files:
        return False, f"corpus directory has no .md files: {groups_dir}", stats

    for filename in files:
        path = os.path.join(groups_dir, filename)
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
        except OSError as exc:
            return False, f"corpus file unreadable: {filename} ({exc.__class__.__name__})", stats
        if not content.strip():
            return False, f"corpus file is empty: {filename}", stats
        if CORPUS_MARKER not in content:
            return False, f"corpus file is missing the {CORPUS_MARKER} marker: {filename}", stats
        if "\n## " not in content and not content.startswith("## "):
            return False, f"corpus file has no '##' sections to chunk: {filename}", stats
        stats["documents"] += 1
        stats["chunks"] += content.count("\n## ") + (1 if content.startswith("## ") else 0)
    stats["marker"] = CORPUS_MARKER

    if manifest_path and os.path.exists(manifest_path):
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
        except (OSError, ValueError) as exc:
            return False, f"corpus manifest unreadable: {exc.__class__.__name__}", stats
        if manifest.get("marker") != CORPUS_MARKER:
            return False, "corpus manifest is missing the SYNTHETIC_DEMO marker", stats
        for filename, meta in (manifest.get("files") or {}).items():
            path = os.path.join(groups_dir, filename)
            if not os.path.exists(path):
                return False, f"corpus manifest lists a missing file: {filename}", stats
            expected = (meta or {}).get("sha256") if isinstance(meta, dict) else None
            if expected:
                with open(path, "rb") as f:
                    actual = hashlib.sha256(f.read()).hexdigest()
                if actual != expected:
                    return False, f"corpus file failed its integrity hash: {filename}", stats

    return True, "", stats


def status() -> dict[str, Any]:
    """Report whether RAG is usable, and why not if it is not.

    ``/api/v1/health`` surfaces this so that a broken RAG stack can never be
    reported as a healthy system.
    """
    if not _enabled():
        return _status_payload("RAG_DISABLED", "ENABLE_RAG_KB is set to false")
    if not _configured:
        return _status_payload("RAG_DISABLED", "RAG corpus was never configured (configure() not called)")
    if _config_error:
        return _status_payload("RAG_ERROR", _config_error)
    if not _groups_dir or not os.path.isdir(_groups_dir):
        return _status_payload("RAG_ERROR", f"configured corpus directory is absent: {_groups_dir}")

    state = "RAG_ENABLED" if _stats.get("documents") else "RAG_ERROR"
    reason = "" if state == "RAG_ENABLED" else "corpus contains no retrievable documents"
    return _status_payload(state, reason)


def _status_payload(state: str, reason: str) -> dict[str, Any]:
    configured = bool(_groups_dir)
    return {
        "state": state,
        "reason": reason,
        "corpus_configured": configured,
        "provider": _active_provider,
        "documents": int(_stats.get("documents", 0)),
        "chunks": int(_stats.get("chunks", 0)),
        "integrity_ok": state == "RAG_ENABLED",
    }


def is_available() -> bool:
    """True only when retrieval can actually return evidence."""
    return status()["state"] == "RAG_ENABLED"


def configure(groups_dir: str, quotes_path: str, validate: bool = True, manifest_path: str | None = None) -> None:
    """Configure the RAG knowledge base. Call before first use.

    The embedding provider is selected from ``RAG_EMBEDDING_PROVIDER``
    (siliconflow | openai | dashscope | ollama | keyword) and defaults to
    ``keyword`` when no key is present, so the offline demo works.

    Raises:
        RagDisabledError: if ``ENABLE_RAG_KB=false``.
        RagCorpusError: if ``validate`` is on and the corpus fails its
            integrity/marker check. The failure is recorded so ``status()``
            reports ``RAG_ERROR`` rather than pretending to be healthy.
    """
    global _groups_dir, _quotes_path, _active_provider, _configured, _config_error, _stats, _retriever

    if not _enabled():
        raise RagDisabledError("cannot configure a RAG corpus while ENABLE_RAG_KB is false")

    if validate:
        ok, reason, stats = validate_corpus(groups_dir, manifest_path)
        if not ok:
            _groups_dir = groups_dir
            _quotes_path = quotes_path
            _configured = True
            _config_error = reason
            _stats = {}
            _retriever = None
            logger.error("RAG corpus rejected: %s", reason)
            raise RagCorpusError(reason)
    else:
        stats = {}

    _groups_dir = groups_dir
    _quotes_path = quotes_path
    _configured = True
    _config_error = ""
    _stats = stats
    _retriever = None
    _active_provider = os.getenv("RAG_EMBEDDING_PROVIDER", "").lower() or _default_provider()
    logger.info(
        "RAG configured: groups_dir=%s, provider=%s, documents=%s",
        groups_dir,
        _active_provider,
        stats.get("documents", "?"),
    )


def initialize_default() -> bool:
    """Initialise the bundled synthetic demo corpus if present.

    Returns True when the default corpus was configured successfully. Errors
    are recorded (so ``status()`` reports them) rather than raised — startup
    must not crash, but it must also not pretend retrieval works.
    """
    if not _enabled():
        logger.info("RAG disabled via ENABLE_RAG_KB=false")
        return False
    if os.path.isdir(DEFAULT_GROUPS_DIR):
        try:
            configure(DEFAULT_GROUPS_DIR, DEFAULT_QUOTES_DIR, manifest_path=DEFAULT_MANIFEST_PATH)
            return True
        except RagCorpusError as exc:
            logger.error("bundled demo corpus failed validation: %s", exc)
            return False
    logger.warning("bundled demo corpus not found at %s — RAG will report an error", DEFAULT_GROUPS_DIR)
    return False


def ensure_default_initialized() -> bool:
    """Lazily initialise the bundled corpus once, if nothing is configured yet.

    The FastAPI lifespan calls :func:`initialize_default` at startup. This is a
    safety net for callers that exercise the service or graph without running
    the lifespan (tests, embedded use) — it never turns a disabled or broken
    RAG into an available one.
    """
    global _default_init_attempted
    if _configured:
        return True
    if not _enabled() or _default_init_attempted:
        return False
    _default_init_attempted = True
    return initialize_default()


def reset() -> None:
    """Clear configuration and cached retriever (used by tests)."""
    global _retriever, _groups_dir, _quotes_path, _active_provider, _configured, _config_error, _stats
    global _default_init_attempted
    _retriever = None
    _groups_dir = ""
    _quotes_path = ""
    _active_provider = "unknown"
    _configured = False
    _config_error = ""
    _stats = {}
    _default_init_attempted = False
    _cache.clear()


def _get_retriever():
    """Lazy-init the KbRetriever singleton with the configured provider."""
    global _retriever
    if _retriever is None:
        if _config_error:
            raise RagCorpusError(_config_error)
        from server.services.kb_retriever import KbRetriever, create_embedding_provider

        provider_name = _active_provider if _active_provider != "unknown" else _default_provider()
        embedder = create_embedding_provider(provider_name)
        try:
            _retriever = KbRetriever(
                groups_dir=_groups_dir,
                quotes_path=_quotes_path,
                embedding_provider=embedder,
            )
        except Exception as exc:  # noqa: BLE001 - surface any init failure as fail-closed
            raise RagUnavailableError(f"retriever init failed: {exc.__class__.__name__}") from exc
        logger.info(
            "KbRetriever initialized: provider=%s, groups=%d, chunks=%d, quotes=%d",
            provider_name,
            len(_retriever._groups),
            len(_retriever._flat_chunks),
            len(_retriever._quotes),
        )
    return _retriever


def _serialize(result: Any) -> dict[str, Any]:
    return {
        "groups": result.groups,
        "group_chunks": [
            {
                "text": c.text,
                "group_id": c.group_id,
                "section_title": c.section_title,
                "start_line": c.start_line,
                "chunk_id": c.chunk_id,
                "source": c.citation_label,
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
        "has_evidence": bool(result.has_evidence),
        "citations": result.citations,
    }


def search(user_msg: str, slots: dict | None = None) -> dict[str, Any]:
    """Search the knowledge base for relevant content.

    Raises:
        RagDisabledError: RAG is switched off.
        RagCorpusError: the configured corpus is missing/corrupt (fail closed).
        RagUnavailableError: retrieval itself failed at runtime.

    Returns:
        dict with keys ``groups``, ``group_chunks``, ``quotes``,
        ``has_evidence`` and ``citations``. An empty ``group_chunks`` with
        ``has_evidence=False`` means the corpus is healthy but holds no
        matching evidence — distinct from an error.
    """
    from server.metrics import record_cache_hit, record_cache_miss

    slots = slots or {}

    if not _configured:
        ensure_default_initialized()

    state = status()["state"]
    if state == "RAG_DISABLED":
        raise RagDisabledError("RAG retrieval requested but unavailable: " + status()["reason"])
    if state == "RAG_ERROR":
        raise RagCorpusError("RAG retrieval requested but corpus is unusable: " + status()["reason"])

    cached = _cache.get(user_msg, slots)
    if cached is not None:
        record_cache_hit()
        return cached

    record_cache_miss()

    try:
        result = _get_retriever().search(user_msg, slots)
    except RagError:
        raise
    except Exception as exc:  # noqa: BLE001 - any retrieval failure is fail-closed
        logger.exception("RAG retrieval failed")
        raise RagUnavailableError(f"retrieval error: {exc.__class__.__name__}") from exc

    response = _serialize(result)
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

    retriever = _retriever
    return _load(user_msg, slots, max_files, kb_retriever=retriever)
