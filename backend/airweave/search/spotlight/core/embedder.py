"""Spotlight query embedder.

Orchestrates embedding based on retrieval strategy.
"""

from airweave.search.spotlight.external.dense_embedder import SpotlightDenseEmbedderInterface
from airweave.search.spotlight.external.sparse_embedder import SpotlightSparseEmbedderInterface
from airweave.search.spotlight.schemas.plan import SpotlightSearchQuery
from airweave.search.spotlight.schemas.query_embeddings import SpotlightQueryEmbeddings
from airweave.search.spotlight.schemas.retrieval_strategy import SpotlightRetrievalStrategy


class SpotlightEmbedder:
    """Orchestrates query embedding based on retrieval strategy.

    Calls the appropriate embedder(s) based on the retrieval strategy:
    - semantic: dense embedder only
    - keyword: sparse embedder only
    - hybrid: both embedders
    """

    def __init__(
        self,
        dense_embedder: SpotlightDenseEmbedderInterface,
        sparse_embedder: SpotlightSparseEmbedderInterface,
    ) -> None:
        """Initialize with embedder interfaces.

        Args:
            dense_embedder: Dense embedder for semantic search.
            sparse_embedder: Sparse embedder for keyword search.
        """
        self._dense_embedder = dense_embedder
        self._sparse_embedder = sparse_embedder

    async def embed(
        self,
        query: SpotlightSearchQuery,
        strategy: SpotlightRetrievalStrategy,
    ) -> SpotlightQueryEmbeddings:
        """Embed query based on retrieval strategy.

        Args:
            query: Search query with primary and optional variations.
            strategy: Retrieval strategy determining which embeddings to create.

        Returns:
            SpotlightQueryEmbeddings with appropriate embeddings populated.
        """
        dense_embeddings = None
        sparse_embedding = None

        # Semantic or hybrid: embed with dense embedder
        if strategy in (
            SpotlightRetrievalStrategy.SEMANTIC,
            SpotlightRetrievalStrategy.HYBRID,
        ):
            dense_embeddings = await self._dense_embedder.embed_batch(query)

        # Keyword or hybrid: embed with sparse embedder
        if strategy in (
            SpotlightRetrievalStrategy.KEYWORD,
            SpotlightRetrievalStrategy.HYBRID,
        ):
            sparse_embedding = await self._sparse_embedder.embed(query)

        return SpotlightQueryEmbeddings(
            dense_embeddings=dense_embeddings,
            sparse_embedding=sparse_embedding,
        )
