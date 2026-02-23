"""Sparse embedder using fastembed BM25 for keyword search."""

import asyncio
from typing import List

from fastembed import SparseTextEmbedding

from airweave.domains.embedders.exceptions import EmbedderProviderError
from airweave.domains.embedders.schemas import SparseEmbedding
from airweave.domains.embedders.sparse.registry import SparseModelSpec
from airweave.platform.sync.async_helpers import run_in_thread_pool


class FastEmbedSparseEmbedder:
    """Sparse embedder using fastembed BM25 (local, no API).

    Uses Qdrant/bm25 model for keyword search.
    Model runs locally, no network calls required.
    """

    def __init__(self, model_spec: SparseModelSpec) -> None:
        """Initialize sparse embedder.

        Args:
            model_spec: Model specification from registry.
        """
        self._model_spec = model_spec
        try:
            self._model = SparseTextEmbedding(model_spec.model_name)
        except Exception as e:
            raise EmbedderProviderError(f"Failed to load sparse embedding model: {e}")

    async def embed(self, text: str) -> SparseEmbedding:
        """Embed a single text for keyword search."""
        if not text:
            raise EmbedderProviderError("Cannot embed empty text")

        results = await self.embed_many([text])
        return results[0]

    async def embed_many(self, texts: list[str]) -> list[SparseEmbedding]:
        """Embed batch of texts for keyword search.

        Fastembed is synchronous, so run in thread pool to avoid blocking.
        """
        if not texts:
            return []

        # Split into sub-batches to allow heartbeats
        MAX_TEXTS_PER_SUBBATCH = 200

        if len(texts) > MAX_TEXTS_PER_SUBBATCH:
            all_embeddings: List[SparseEmbedding] = []
            for i in range(0, len(texts), MAX_TEXTS_PER_SUBBATCH):
                sub_batch = texts[i : i + MAX_TEXTS_PER_SUBBATCH]
                sub_embeddings = await self.embed_many(sub_batch)
                all_embeddings.extend(sub_embeddings)
                await asyncio.sleep(0)
            return all_embeddings

        try:

            def _embed_sync() -> list[SparseEmbedding]:
                raw_embeddings = list(self._model.embed(texts))
                if len(raw_embeddings) != len(texts):
                    raise ValueError(f"Got {len(raw_embeddings)} embeddings for {len(texts)} texts")
                return [
                    SparseEmbedding(
                        indices=emb.indices.tolist(),
                        values=emb.values.tolist(),
                    )
                    for emb in raw_embeddings
                ]

            return await run_in_thread_pool(_embed_sync)

        except Exception as e:
            raise EmbedderProviderError(f"Sparse embedding failed: {e}")

    async def close(self) -> None:
        """No-op — fastembed doesn't need explicit cleanup."""
