"""Sparse embedder using fastembed BM25 for keyword search."""

from typing import List

from fastembed import SparseEmbedding, SparseTextEmbedding

from airweave.platform.sync.async_helpers import run_in_thread_pool
from airweave.platform.sync.context import SyncContext
from airweave.platform.sync.exceptions import SyncFailureError

from ._base import BaseEmbedder


class SparseEmbedder(BaseEmbedder):
    """Singleton sparse embedder using fastembed BM25 (local, no API).

    Uses Qdrant/bm25 model for keyword search.
    Model runs locally, no network calls required.
    """

    MODEL_NAME = "Qdrant/bm25"

    def __init__(self):
        """Initialize sparse embedder (once per pod)."""
        if self._initialized:
            return

        try:
            self._model = SparseTextEmbedding(self.MODEL_NAME)
            self._initialized = True
        except Exception as e:
            raise SyncFailureError(f"Failed to load sparse embedding model: {e}")

    async def embed_many(
        self, texts: List[str], sync_context: SyncContext
    ) -> List[SparseEmbedding]:
        """Embed batch of texts for keyword search.

        Returns exactly len(texts) SparseEmbedding objects.
        Fastembed is synchronous, so run in thread pool to avoid blocking event loop.

        Args:
            texts: List of text strings to embed
            sync_context: Sync context with logger

        Returns:
            List of SparseEmbedding objects

        Raises:
            SyncFailureError: On any error
        """
        if not texts:
            return []

        try:

            def _embed_sync():
                """Synchronous embedding (run in thread pool)."""
                embeddings = list(self._model.embed(texts))
                if len(embeddings) != len(texts):
                    raise ValueError(f"Got {len(embeddings)} embeddings for {len(texts)} texts")
                return embeddings

            return await run_in_thread_pool(_embed_sync)

        except Exception as e:
            sync_context.logger.error(f"Sparse embedding failed: {e}")
            raise SyncFailureError(f"Sparse embedding failed: {e}")
