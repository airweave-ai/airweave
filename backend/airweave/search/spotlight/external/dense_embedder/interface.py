"""Dense embedder interface for spotlight search."""

from typing import Protocol

from airweave.search.spotlight.external.dense_embedder.registry import (
    DenseEmbedderModelSpec,
)
from airweave.search.spotlight.schemas.plan import SpotlightSearchQuery
from airweave.search.spotlight.schemas.query_embeddings import SpotlightDenseEmbedding


class SpotlightDenseEmbedderInterface(Protocol):
    """Interface for dense (semantic) embedding.

    Embeds primary query and variations for vector similarity search.
    The model_spec and vector_size are provided at initialization time.
    """

    @property
    def model_spec(self) -> DenseEmbedderModelSpec:
        """Get the model specification."""
        ...

    async def embed_batch(self, query: SpotlightSearchQuery) -> list[SpotlightDenseEmbedding]:
        """Embed primary query and all variations.

        Args:
            query: Search query containing primary and optional variations.

        Returns:
            List of dense embeddings, one per query text.
            Order: [primary_embedding, variation_1_embedding, ...].
        """
        ...

    async def close(self) -> None:
        """Clean up resources."""
        ...
