"""AgenticSearch query embedder.

Orchestrates embedding based on retrieval strategy.
"""

from airweave.search.agentic_search.external.dense_embedder import (
    AgenticSearchDenseEmbedderInterface,
)
from airweave.search.agentic_search.external.sparse_embedder import (
    AgenticSearchSparseEmbedderInterface,
)
from airweave.search.agentic_search.schemas.plan import AgenticSearchQuery
from airweave.search.agentic_search.schemas.query_embeddings import AgenticSearchQueryEmbeddings
from airweave.search.agentic_search.schemas.retrieval_strategy import AgenticSearchRetrievalStrategy


class AgenticSearchEmbedder:
    """Orchestrates query embedding based on retrieval strategy.

    Calls the appropriate embedder(s) based on the retrieval strategy:
    - semantic: dense embedder only
    - keyword: sparse embedder only
    - hybrid: both embedders
    """

    def __init__(
        self,
        dense_embedder: AgenticSearchDenseEmbedderInterface,
        sparse_embedder: AgenticSearchSparseEmbedderInterface,
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
        query: AgenticSearchQuery,
        strategy: AgenticSearchRetrievalStrategy,
    ) -> AgenticSearchQueryEmbeddings:
        """Embed query based on retrieval strategy.

        Args:
            query: Search query with primary and optional variations.
            strategy: Retrieval strategy determining which embeddings to create.

        Returns:
            AgenticSearchQueryEmbeddings with appropriate embeddings populated.
        """
        dense_embeddings = None
        sparse_embedding = None

        # Semantic or hybrid: embed with dense embedder
        if strategy in (
            AgenticSearchRetrievalStrategy.SEMANTIC,
            AgenticSearchRetrievalStrategy.HYBRID,
        ):
            dense_embeddings = await self._dense_embedder.embed_batch(query)

        # Keyword or hybrid: embed with sparse embedder
        if strategy in (
            AgenticSearchRetrievalStrategy.KEYWORD,
            AgenticSearchRetrievalStrategy.HYBRID,
        ):
            sparse_embedding = await self._sparse_embedder.embed(query)

        return AgenticSearchQueryEmbeddings(
            dense_embeddings=dense_embeddings,
            sparse_embedding=sparse_embedding,
        )
