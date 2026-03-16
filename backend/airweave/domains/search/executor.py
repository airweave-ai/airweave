"""Search plan executor — shared pipeline for all search tiers.

Merge filters -> embed query -> compile DB query -> execute -> SearchResults.
"""

from __future__ import annotations

from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.domains.search.adapters.vector_db.protocol import VectorDBProtocol
from airweave.domains.search.builders.search_plan import SearchPlanBuilder
from airweave.domains.search.protocols import SearchPlanExecutorProtocol
from airweave.domains.search.types import (
    FilterGroup,
    QueryEmbeddings,
    RetrievalStrategy,
    SearchPlan,
    SearchResults,
)


class SearchPlanExecutor(SearchPlanExecutorProtocol):
    """Executes a search plan against the vector database.

    Pipeline:
    1. Merge plan filters with user-supplied filters
    2. Embed query based on retrieval strategy
    3. Compile into DB-specific query
    4. Execute and return results
    """

    def __init__(
        self,
        dense_embedder: DenseEmbedderProtocol,
        sparse_embedder: SparseEmbedderProtocol,
        vector_db: VectorDBProtocol,
    ) -> None:
        """Initialize with embedders and vector database."""
        self._dense_embedder = dense_embedder
        self._sparse_embedder = sparse_embedder
        self._vector_db = vector_db

    async def execute(
        self,
        plan: SearchPlan,
        user_filter: list[FilterGroup],
        collection_id: str,
    ) -> SearchResults:
        """Execute the full search pipeline."""
        # 1. Merge plan filters with user filters
        complete_plan = SearchPlanBuilder.build(plan, user_filter)

        # 2. Embed based on retrieval strategy
        dense_embeddings = None
        sparse_embedding = None

        if complete_plan.retrieval_strategy in (
            RetrievalStrategy.SEMANTIC,
            RetrievalStrategy.HYBRID,
        ):
            texts = [complete_plan.query.primary] + list(complete_plan.query.variations)
            dense_embeddings = await self._dense_embedder.embed_many(texts)

        if complete_plan.retrieval_strategy in (
            RetrievalStrategy.KEYWORD,
            RetrievalStrategy.HYBRID,
        ):
            sparse_embedding = await self._sparse_embedder.embed(complete_plan.query.primary)

        embeddings = QueryEmbeddings(
            dense_embeddings=dense_embeddings,
            sparse_embedding=sparse_embedding,
        )

        # 3. Compile
        compiled_query = await self._vector_db.compile_query(
            plan=complete_plan,
            embeddings=embeddings,
            collection_id=collection_id,
        )

        # 4. Execute
        return await self._vector_db.execute_query(compiled_query)
