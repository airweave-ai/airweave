"""AgenticSearch query embedder.

Orchestrates embedding based on retrieval strategy.
Uses domain embedder protocols directly.
"""

from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.search.agentic_search.schemas.plan import AgenticSearchQuery
from airweave.search.agentic_search.schemas.query_embeddings import (
    AgenticSearchDenseEmbedding,
    AgenticSearchQueryEmbeddings,
    AgenticSearchSparseEmbedding,
)
from airweave.search.agentic_search.schemas.retrieval_strategy import AgenticSearchRetrievalStrategy


class AgenticSearchEmbedder:
    """Orchestrates query embedding based on retrieval strategy.

    Calls the domain embedder protocols directly:
    - semantic: dense embedder only
    - keyword: sparse embedder only
    - hybrid: both embedders
    """

    def __init__(
        self,
        dense_embedder: DenseEmbedderProtocol,
        sparse_embedder: SparseEmbedderProtocol,
    ) -> None:
        """Initialize with dense and sparse embedders."""
        self._dense_embedder = dense_embedder
        self._sparse_embedder = sparse_embedder

    async def embed(
        self,
        query: AgenticSearchQuery,
        strategy: AgenticSearchRetrievalStrategy,
    ) -> AgenticSearchQueryEmbeddings:
        """Embed query based on retrieval strategy."""
        dense_embeddings = None
        sparse_embedding = None

        # Semantic or hybrid: embed all variations with dense embedder
        if strategy in (
            AgenticSearchRetrievalStrategy.SEMANTIC,
            AgenticSearchRetrievalStrategy.HYBRID,
        ):
            texts = [query.primary] + list(query.variations)
            domain_embeddings = await self._dense_embedder.embed_many(texts)
            dense_embeddings = [
                AgenticSearchDenseEmbedding(vector=emb.vector) for emb in domain_embeddings
            ]

        # Keyword or hybrid: embed primary with sparse embedder
        if strategy in (
            AgenticSearchRetrievalStrategy.KEYWORD,
            AgenticSearchRetrievalStrategy.HYBRID,
        ):
            domain_sparse = await self._sparse_embedder.embed(query.primary)
            sparse_embedding = AgenticSearchSparseEmbedding(
                indices=domain_sparse.indices,
                values=domain_sparse.values,
            )

        return AgenticSearchQueryEmbeddings(
            dense_embeddings=dense_embeddings,
            sparse_embedding=sparse_embedding,
        )
