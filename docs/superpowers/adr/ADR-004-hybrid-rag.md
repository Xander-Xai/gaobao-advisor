# ADR-004: Hybrid RAG (Vector + Keyword) for Knowledge Retrieval

**Status:** Accepted (implemented; synthetic demo corpus enabled by default)
**Date:** 2026-06
**Updated:** 2026-10 — the public demo now ships an original SYNTHETIC_DEMO
corpus and enables RAG by default; the keyword path is a BM25 implementation.

## Context
Gaokao advice requires factual recall of:
- School rankings, admission scores, major details
- Domain guidance and analysis frameworks
- Policy rules and cutoff lines

Pure vector search misses exact keyword matches (score thresholds, school names).
Pure keyword search misses semantic similarity.

## Decision
Implement hybrid RAG: vector similarity (embedding) + BM25 keyword retrieval.
Configurable embedding provider (SiliconFlow by default for Chinese quality).

The public demo ships an **original, machine-authored, synthetic** corpus under
`knowledge/synthetic_demo/`. RAG is enabled by default against it, and the
corpus is validated (marker + optional sha256 manifest) on startup. The BM25
keyword path needs no key, no network and no model, so the demo works offline.

## Consequences
+ Higher recall than single-strategy retrieval
+ BM25 keyword path always available; dense path is optional
+ Evidence fragments carry stable `chunk_id` / `source` markers for citation
+ No evidence returns `has_evidence=false` with an anti-fabrication instruction,
  rather than a confident unsourced answer
+ Graceful degradation — if the vector DB is unavailable, keyword search runs
+ Fail-closed — a missing/corrupt/unmarked corpus yields `RAG_ERROR` and raises,
  never a silent empty-but-successful result
- Requires embedding model for the dense path (Chinese BGE model, 1GB+); the
  demo does not need it
- Cold-start issue for new content (needs reindexing)
- The shipped corpus is synthetic and deliberately small; the labeled-set
  hit-rate (12/12) is a wiring check, not a production quality benchmark