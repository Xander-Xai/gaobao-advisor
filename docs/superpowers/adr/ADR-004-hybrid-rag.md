# ADR-004: Hybrid RAG (Vector + Keyword) for Knowledge Retrieval

**Status:** Accepted (implemented)
**Date:** 2026-06

## Context
Gaokao advice requires factual recall of:
- School rankings, admission scores, major details
- Zhang Xuefeng quotes and analysis frameworks
- Policy rules and cutoff lines

Pure vector search misses exact keyword matches (score thresholds, school names).
Pure keyword search misses semantic similarity.

## Decision
Implement hybrid RAG: vector similarity (embedding) + keyword BM25-style retrieval.
Configurable embedding provider (SiliconFlow by default for Chinese quality).

## Consequences
+ Higher recall than single-strategy retrieval
+ Graceful degradation — if vector DB unavailable, falls back to keyword
+ Embedding compute is offline (precomputed)
- Requires embedding model (Chinese BGE model, 1GB+)
- Cold-start issue for new content (needs reindexing)