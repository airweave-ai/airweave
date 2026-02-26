"""Sparse embedder interface for agentic search."""

from typing import Protocol

from airweave.search.agentic_search.external.sparse_embedder.registry import (
    SparseEmbedderModelSpec,
)
from airweave.search.agentic_search.schemas.plan import AgenticSearchQuery
from airweave.search.agentic_search.schemas.query_embeddings import AgenticSearchSparseEmbedding


class AgenticSearchSparseEmbedderInterface(Protocol):
    """Interface for sparse (keyword/BM25) embedding.

    Embeds only the primary query for keyword matching.
    Sparse embeddings produce (token_id, weight) pairs - the dimension
    is determined by the vocabulary, not configurable.
    """

    @property
    def model_spec(self) -> SparseEmbedderModelSpec:
        """Get the model specification."""
        ...

    async def embed(self, query: AgenticSearchQuery) -> AgenticSearchSparseEmbedding:
        """Embed the primary query.

        Args:
            query: Search query (only primary is used).

        Returns:
            Sparse embedding for keyword/BM25 search.
        """
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...
