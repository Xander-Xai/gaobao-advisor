#!/usr/bin/env python3
"""
预计算知识组 + 语录的 embedding 向量，存为 .npy 文件。

用法:
    python scripts/precompute_embeddings.py [--provider openai|dashscope|ollama]

生成文件:
    knowledge/quotes/embeddings.npy   — 语录向量矩阵 (N × dim)
    knowledge/quotes/quote_meta.json  — 语录元数据索引
    knowledge/quotes/group_embeddings.npy — 知识组 chunks 向量矩阵
    knowledge/quotes/group_meta.json  — 知识组 chunks 元数据
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

from kb_retriever import (
    load_all_groups, create_embedding_provider,
)

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)


def precompute_groups(groups_dir: str, embedder, output_dir: str) -> None:
    """预计算知识组 chunks 的 embedding。"""
    all_groups = load_all_groups(groups_dir)
    all_texts: list[str] = []
    metadata: list[dict] = []

    for group_id, chunks in all_groups.items():
        for i, chunk in enumerate(chunks):
            all_texts.append(chunk.text)
            metadata.append({
                "group_id": group_id,
                "chunk_index": i,
                "section_title": chunk.section_title,
                "start_line": chunk.start_line,
            })

    if not all_texts:
        print("No group chunks found.")
        return

    print(f"Embedding {len(all_texts)} group chunks...")
    embeddings = embedder.embed(all_texts)
    valid = [e for e in embeddings if e is not None]
    if not valid:
        print("ERROR: All embeddings are None.")
        return
    emb_matrix = np.stack(valid)

    out_path = os.path.join(output_dir, "group_embeddings.npy")
    np.save(out_path, emb_matrix.astype(np.float32))
    print(f"Saved: {out_path} ({emb_matrix.shape})")

    meta_path = os.path.join(output_dir, "group_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"Saved: {meta_path}")


def precompute_quotes(quotes_path: str, embedder) -> None:
    """预计算语录的 embedding。"""
    index_path = os.path.join(quotes_path, "_by_major.json")
    with open(index_path, "r", encoding="utf-8") as f:
        raw_index: dict = json.load(f)

    all_texts: list[str] = []
    metadata: list[dict] = []

    for major_key, quote_list in raw_index.items():
        for q in quote_list:
            all_texts.append(q["text"])
            metadata.append({
                "id": q.get("id", ""),
                "text": q["text"],
                "major": major_key,
                "tags": q.get("tags", []),
                "category": q.get("category", ""),
                "sentiment": q.get("sentiment", ""),
            })

    if not all_texts:
        print("No quotes found.")
        return

    print(f"Embedding {len(all_texts)} quotes...")
    embeddings = embedder.embed(all_texts)
    valid = [e for e in embeddings if e is not None]
    if not valid:
        print("ERROR: All embeddings are None.")
        return
    emb_matrix = np.stack(valid)

    out_path = os.path.join(quotes_path, "embeddings.npy")
    np.save(out_path, emb_matrix.astype(np.float32))
    print(f"Saved: {out_path} ({emb_matrix.shape})")

    meta_path = os.path.join(quotes_path, "quote_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"Saved: {meta_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Precompute embeddings for knowledge retrieval")
    parser.add_argument("--provider", default="openai",
                        choices=["openai", "dashscope", "ollama"],
                        help="Embedding provider (default: openai)")
    parser.add_argument("--model", default=None, help="Embedding model name")
    args = parser.parse_args()

    embedder = create_embedding_provider(provider=args.provider, model=args.model)

    groups_dir = os.path.join(PROJECT_ROOT, "knowledge", "groups")
    quotes_path = os.path.join(PROJECT_ROOT, "knowledge", "quotes")

    if os.path.isdir(groups_dir):
        precompute_groups(groups_dir, embedder, quotes_path)
    else:
        print(f"Groups directory not found: {groups_dir}")

    if os.path.isdir(quotes_path):
        precompute_quotes(quotes_path, embedder)
    else:
        print(f"Quotes directory not found: {quotes_path}")


if __name__ == "__main__":
    main()
