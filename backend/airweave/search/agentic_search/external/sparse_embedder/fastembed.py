"""FastEmbed sparse embedder for agentic search.

Uses sparse embedding models for keyword/BM25 search.
Model runs locally, no network calls required.
"""

import asyncio

from fastembed import SparseTextEmbedding

from airweave.search.agentic_search.external.sparse_embedder.registry import (
    SparseEmbedderModelSpec,
)
from airweave.search.agentic_search.schemas.plan import AgenticSearchQuery
from airweave.search.agentic_search.schemas.query_embeddings import AgenticSearchSparseEmbedding


class FastEmbedSparseEmbedder:
    """FastEmbed sparse embedder for agentic search.

    Uses a sparse embedding model for keyword search.
    Model runs locally - no API calls, no rate limiting needed.

    Features:
    - Local model (no API calls)
    - Async via thread pool (fastembed is synchronous)
    - Fail-fast on errors
    """

    def __init__(self, model_spec: SparseEmbedderModelSpec) -> None:
        """Initialize the sparse embedder.

        Loads the sparse embedding model. This may take a moment
        on first run as the model needs to be downloaded.

        Args:
            model_spec: Model specification from the registry.

        Raises:
            RuntimeError: If model loading fails.
        """
        self._model_spec = model_spec

        try:
            self._model = SparseTextEmbedding(model_spec.model_name)
        except Exception as e:
            raise RuntimeError(
                f"Failed to load sparse embedding model '{model_spec.model_name}': {e}"
            ) from e

    @property
    def model_spec(self) -> SparseEmbedderModelSpec:
        """Get the model specification."""
        return self._model_spec

    async def embed(self, query: AgenticSearchQuery) -> AgenticSearchSparseEmbedding:
        """Embed the primary query for keyword search.

        Only the primary query is embedded (sparse search doesn't use variations).
        Fastembed is synchronous, so we run it in a thread pool.

        Args:
            query: Search query (only primary is used).

        Returns:
            Sparse embedding with token indices and weights.

        Raises:
            ValueError: If primary query is empty.
            RuntimeError: If embedding fails.
        """
        text = query.primary
        if not text or not text.strip():
            raise ValueError("Cannot embed empty query text")

        try:
            # Run sync embedding in thread pool to avoid blocking event loop
            embedding = await asyncio.to_thread(self._embed_sync, text)

            return AgenticSearchSparseEmbedding(
                indices=embedding.indices.tolist(),
                values=embedding.values.tolist(),
            )
        except Exception as e:
            raise RuntimeError(f"Sparse embedding failed: {e}") from e

    def _embed_sync(self, text: str):
        """Synchronous embedding (called in thread pool).

        Args:
            text: Text to embed.

        Returns:
            SparseEmbedding from fastembed.
        """
        # embed() returns a generator, we only have one text
        embeddings = list(self._model.embed([text]))
        if len(embeddings) != 1:
            raise ValueError(f"Expected 1 embedding, got {len(embeddings)}")
        return embeddings[0]

    async def close(self) -> None:
        """Clean up resources.

        FastEmbed doesn't require explicit cleanup,
        but we implement this for interface compliance.
        """
        pass
