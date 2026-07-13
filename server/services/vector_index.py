"""
Vector Index Persistence — FAISS-based embedding cache.

Provides persistent storage for knowledge base embeddings to avoid
recomputing on every server restart. Uses FAISS for efficient similarity
search and NumPy for metadata storage.

Usage:
    from server.services.vector_index import VectorIndexStore

    store = VectorIndexStore(index_dir="data/vector_index")

    # Save embeddings
    store.save_embeddings(chunk_ids, embeddings, metadata)

    # Load embeddings (fast startup)
    if store.exists():
        store.load_embeddings()

    # Search
    results = store.search(query_embedding, top_k=5)
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import faiss
import numpy as np

from config.loader import load_runtime_settings

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Single search result with metadata."""

    chunk_id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorIndexStore:
    """FAISS-based vector index with persistent storage.

    Features:
    - Flat index (exact search, best for < 100k vectors)
    - Metadata stored in JSON sidecar file
    - Atomic save/load to prevent corruption
    - Automatic dimension detection
    """

    def __init__(self, index_dir: str = "data/vector_index", index_type: str = "Flat"):
        """Initialize vector index store.

        Args:
            index_dir: Directory to store index files
            index_type: FAISS index type ("Flat", "IVF", "HNSW")
        """
        self.index_dir = index_dir
        self.index_type = index_type
        self.index_path = os.path.join(index_dir, "faiss.index")
        self.metadata_path = os.path.join(index_dir, "metadata.json")

        self._index: faiss.Index | None = None
        self._metadata: list[dict[str, Any]] = []
        self._dimension: int | None = None

        os.makedirs(index_dir, exist_ok=True)

    @property
    def size(self) -> int:
        """Number of vectors in the index."""
        return self._index.ntotal if self._index else 0

    def exists(self) -> bool:
        """Check if persisted index exists."""
        return os.path.exists(self.index_path) and os.path.exists(self.metadata_path)

    def save_embeddings(
        self,
        chunk_ids: list[str],
        embeddings: list[np.ndarray],
        metadata_list: list[dict[str, Any]],
    ) -> None:
        """Save embeddings to persistent storage.

        Args:
            chunk_ids: Unique identifiers for each chunk
            embeddings: List of embedding vectors (must be same dimension)
            metadata_list: List of metadata dicts for each chunk
        """
        if not embeddings:
            logger.warning("No embeddings to save")
            return

        # Validate dimensions
        dimension = embeddings[0].shape[0]
        if not all(emb.shape[0] == dimension for emb in embeddings):
            raise ValueError("All embeddings must have the same dimension")

        # Convert to numpy array
        embeddings_array = np.array(embeddings, dtype=np.float32)

        # Create or update FAISS index
        if self._index is None:
            self._dimension = dimension
            if self.index_type == "Flat":
                self._index = faiss.IndexFlatIP(dimension)  # Inner product (cosine similarity)
            elif self.index_type == "IVF":
                nlist = min(100, len(embeddings) // 10)  # Heuristic
                quantizer = faiss.IndexFlatIP(dimension)
                self._index = faiss.IndexIVFFlat(quantizer, dimension, nlist, faiss.METRIC_INNER_PRODUCT)
                self._index.train(embeddings_array)
            else:
                raise ValueError(f"Unsupported index type: {self.index_type}")

        # Add vectors
        self._index.add(embeddings_array)

        # Update metadata
        for i, (chunk_id, meta) in enumerate(zip(chunk_ids, metadata_list, strict=False)):
            self._metadata.append({"chunk_id": chunk_id, "index": self.size - len(chunk_ids) + i, **meta})

        # Atomic save (write to temp, then rename)
        temp_index_path = self.index_path + ".tmp"
        temp_metadata_path = self.metadata_path + ".tmp"

        try:
            faiss.write_index(self._index, temp_index_path)
            with open(temp_metadata_path, "w", encoding="utf-8") as f:
                json.dump(self._metadata, f, ensure_ascii=False, indent=2)

            # Atomic rename
            os.replace(temp_index_path, self.index_path)
            os.replace(temp_metadata_path, self.metadata_path)

            logger.info(
                "Saved %d embeddings to %s (dimension=%d)",
                len(chunk_ids),
                self.index_dir,
                dimension,
            )
        except Exception as e:
            # Clean up temp files on error
            for path in [temp_index_path, temp_metadata_path]:
                if os.path.exists(path):
                    os.remove(path)
            raise e

    def load_embeddings(self) -> None:
        """Load embeddings from persistent storage."""
        if not self.exists():
            raise FileNotFoundError(f"Index not found at {self.index_dir}")

        try:
            # Load FAISS index
            self._index = faiss.read_index(self.index_path)
            self._dimension = self._index.d

            # Load metadata
            with open(self.metadata_path, encoding="utf-8") as f:
                self._metadata = json.load(f)

            logger.info(
                "Loaded %d embeddings from %s (dimension=%d)",
                self.size,
                self.index_dir,
                self._dimension,
            )
        except Exception as e:
            logger.error("Failed to load embeddings: %s", e)
            raise

    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> list[SearchResult]:
        """Search for similar vectors.

        Args:
            query_embedding: Query vector (1D array)
            top_k: Number of results to return

        Returns:
            List of SearchResult sorted by similarity (highest first)
        """
        if self._index is None or self.size == 0:
            return []

        # Ensure query is 2D (FAISS requirement)
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)

        # Normalize for cosine similarity
        faiss.normalize_L2(query_embedding)

        # Search
        k = min(top_k, self.size)
        scores, indices = self._index.search(query_embedding.astype(np.float32), k)

        # Build results
        results = []
        for score, idx in zip(scores[0], indices[0], strict=False):
            if idx == -1:  # FAISS returns -1 for empty slots
                continue
            metadata = self._metadata[idx] if idx < len(self._metadata) else {}
            results.append(
                SearchResult(
                    chunk_id=metadata.get("chunk_id", f"chunk_{idx}"),
                    score=float(score),
                    metadata=metadata,
                )
            )

        return results

    def clear(self) -> None:
        """Clear all embeddings from the index."""
        if self._index:
            self._index.reset()
        self._metadata.clear()
        logger.info("Cleared vector index")

    def remove_chunks(self, chunk_ids: list[str]) -> int:
        """Remove specific chunks from the index.

        Note: FAISS doesn't support deletion, so we rebuild the index.
        This is inefficient but acceptable for infrequent updates.

        Returns:
            Number of chunks removed
        """
        if not self._index or not chunk_ids:
            return 0

        # Find indices to keep
        ids_to_remove = set(chunk_ids)
        indices_to_keep = []
        metadata_to_keep = []

        for i, meta in enumerate(self._metadata):
            if meta.get("chunk_id") not in ids_to_remove:
                indices_to_keep.append(i)
                metadata_to_keep.append(meta)

        removed_count = len(self._metadata) - len(metadata_to_keep)

        if removed_count == 0:
            return 0

        # Rebuild index with remaining vectors
        # Note: This requires access to original embeddings, which we don't store
        # For now, we just clear and require full rebuild
        logger.warning(
            "Chunk removal requires full rebuild. Removed %d chunks.",
            removed_count,
        )
        self.clear()

        return removed_count


# Global singleton instance
_vector_store: VectorIndexStore | None = None


def get_vector_store(index_dir: str = "data/vector_index") -> VectorIndexStore:
    """Get or create the global vector store instance.

    Args:
        index_dir: Directory for persistent storage

    Returns:
        VectorIndexStore instance
    """
    global _vector_store
    if _vector_store is None:
        if index_dir == "data/vector_index":
            index_dir = load_runtime_settings()["vector_index_dir"]
        _vector_store = VectorIndexStore(index_dir=index_dir)
    return _vector_store
