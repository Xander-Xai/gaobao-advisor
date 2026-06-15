#!/usr/bin/env python3
"""End-to-end RAG verification: SiliconFlow bge-large-zh-v1.5 → KbRetriever.

Run: python3 scripts/verify_rag_siliconflow.py
Exits 0 on success, 1 on failure. Prints what was actually retrieved.
"""

import os
import sys
import time

# Load .env manually (no python-dotenv dependency)
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.isfile(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# Sanity check: do we have the API key?
api_key = os.getenv("SILICONFLOW_API_KEY", "")
if not api_key or api_key.startswith("sk-your"):
    print("ERROR: SILICONFLOW_API_KEY not set in .env", file=sys.stderr)
    sys.exit(1)

# Override to siliconflow (ignore the env-var auto-detection default)
os.environ["RAG_EMBEDDING_PROVIDER"] = "siliconflow"

from kb_retriever import KbRetriever, create_embedding_provider  # noqa: E402

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_groups_dir = os.path.join(_project_root, "knowledge", "groups")
_quotes_path = os.path.join(_project_root, "knowledge", "quotes")

print("=" * 60)
print("Step 1: Creating SiliconFlow embedding provider")
print("=" * 60)
embedder = create_embedding_provider("siliconflow")
print(f"  Provider: {type(embedder).__name__}")
print(f"  Model:    {embedder._model}")
print(f"  Base URL: {embedder._client.base_url}")

# Smoke-test a single embedding call BEFORE building the retriever,
# to surface API errors clearly (the retriever swallows them).
print()
print("Smoke test: embedding 2 short queries...")
try:
    test_vecs = embedder.embed(["测试文本A", "测试文本B"])
    print(f"  ✅ Got {len(test_vecs)} vectors, dim={test_vecs[0].shape[0]}")
except Exception as e:
    print(f"  ❌ Embedding smoke test failed: {type(e).__name__}: {e}")
    sys.exit(1)
print()

print("=" * 60)
print("Step 2: Building KbRetriever (this calls embedding API)")
print("=" * 60)
t0 = time.time()
retriever = KbRetriever(
    groups_dir=_groups_dir,
    quotes_path=_quotes_path,
    embedding_provider=embedder,
)
t1 = time.time()
print(f"  Groups loaded:  {list(retriever._groups.keys())}")
print(f"  Total chunks:   {sum(len(c) for c in retriever._groups.values())}")
print(f"  Total quotes:   {len(retriever._quotes)}")
print(f"  Init time:      {t1 - t0:.2f}s")
print()

# Verify embeddings are real (not all-zero from KeywordOnlyEmbedding)
sample = retriever._groups["G1_core_method"][0]
if sample.embedding is None:
    print("ERROR: chunk embedding is None — embedding call failed", file=sys.stderr)
    sys.exit(1)
if not sample.embedding.any():
    print("ERROR: chunk embedding is all-zero — provider is in keyword fallback mode", file=sys.stderr)
    sys.exit(1)
print(
    f"  Sample chunk embedding: shape={sample.embedding.shape}, "
    f"norm={float((sample.embedding**2).sum() ** 0.5):.4f}, "
    f"non-zero={int((sample.embedding != 0).sum())}/{sample.embedding.size}"
)
print()

print("=" * 60)
print("Step 3: Search 3 test queries")
print("=" * 60)
test_queries = [
    ("我考了580分,想学人工智能,应该怎么报志愿?", {"province": "山东", "score": 580}),
    ("电气工程专业怎么样?就业前景好不好?", {}),
    ("考研和直接就业哪个好?", {}),
]
for q, slots in test_queries:
    t0 = time.time()
    result = retriever.search(q, slots)
    t1 = time.time()
    print(f"\nQuery: {q}")
    print(f"  Slots: {slots}")
    print(f"  Search time: {(t1 - t0) * 1000:.0f}ms")
    print(f"  Selected groups: {result.groups}")
    print(f"  Top chunks ({len(result.group_chunks)}):")
    for i, c in enumerate(result.group_chunks[:2], 1):
        preview = c.text.replace("\n", " ")[:80]
        print(f"    [{i}] {c.group_id} > {c.section_title[:30]}: {preview}...")
    print(f"  Top quotes ({len(result.quotes)}):")
    for i, q in enumerate(result.quotes[:2], 1):
        print(f"    [{i}] {q.major}: {q.text[:60]}...")

print()
print("=" * 60)
print("✅ All checks passed. Real vector RAG is operational.")
print("=" * 60)
