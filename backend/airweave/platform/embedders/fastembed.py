"""Sparse embedder using fastembed BM25 for keyword search."""

import asyncio
from typing import List

from fastembed import SparseEmbedding, SparseTextEmbedding

from airweave.platform.contexts import SyncContext
from airweave.platform.sync.async_helpers import run_in_thread_pool
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
        self, texts: List[str], sync_context: SyncContext = None
    ) -> List[SparseEmbedding]:
        """Embed batch of texts for keyword search.

        Returns exactly len(texts) SparseEmbedding objects.
        Fastembed is synchronous, so run in thread pool to avoid blocking event loop.

        Args:
            texts: List of text strings to embed
            sync_context: Optional sync context with logger (for sync operations)

        Returns:
            List of SparseEmbedding objects

        Raises:
            SyncFailureError: On any error
        """
        if not texts:
            return []

        # Split into smaller batches to avoid blocking and allow heartbeats
        # Max 200 texts per sub-batch to prevent long blocking periods
        MAX_TEXTS_PER_SUBBATCH = 200

        if len(texts) > MAX_TEXTS_PER_SUBBATCH:
            if sync_context and hasattr(sync_context, "logger"):
                sync_context.logger.debug(
                    f"Splitting {len(texts)} texts into sub-batches of {MAX_TEXTS_PER_SUBBATCH} "
                    f"to allow heartbeats and prevent Temporal timeout"
                )
            all_embeddings = []
            for i in range(0, len(texts), MAX_TEXTS_PER_SUBBATCH):
                sub_batch = texts[i : i + MAX_TEXTS_PER_SUBBATCH]
                sub_embeddings = await self.embed_many(sub_batch, sync_context)
                all_embeddings.extend(sub_embeddings)
                # Yield control to event loop between sub-batches
                await asyncio.sleep(0)
            return all_embeddings

        try:

            def _embed_sync():
                """Synchronous embedding (run in thread pool)."""
                embeddings = list(self._model.embed(texts))
                if len(embeddings) != len(texts):
                    raise ValueError(f"Got {len(embeddings)} embeddings for {len(texts)} texts")
                return embeddings

            return await run_in_thread_pool(_embed_sync)

        except Exception as e:
            if sync_context and hasattr(sync_context, "logger"):
                sync_context.logger.error(f"Sparse embedding failed: {e}")
            raise SyncFailureError(f"Sparse embedding failed: {e}")

    async def embed(self, text: str) -> SparseEmbedding:
        """Embed single text for keyword search.

        Convenience method for single text embedding (used by search module).

        Args:
            text: Text string to embed

        Returns:
            SparseEmbedding object

        Raises:
            SyncFailureError: On any error
        """
        if not text:
            raise SyncFailureError("Cannot embed empty text")

        embeddings = await self.embed_many([text])
        return embeddings[0]
