"""Vespa vector database client for spotlight search.

Handles query compilation (plan + embeddings → YQL) and execution.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, Optional

from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.search.spotlight.external.vector_database.vespa.config import (
    ALL_VESPA_SCHEMAS,
    DEFAULT_GLOBAL_PHASE_RERANK_COUNT,
    HNSW_EXPLORE_ADDITIONAL,
    TARGET_HITS,
)
from airweave.search.spotlight.external.vector_database.vespa.filter_translator import (
    FilterTranslator,
)
from airweave.search.spotlight.schemas.plan import SpotlightPlan
from airweave.search.spotlight.schemas.query_embeddings import (
    SpotlightQueryEmbeddings,
    SpotlightSparseEmbedding,
)
from airweave.search.spotlight.schemas.retrieval_strategy import SpotlightRetrievalStrategy
from airweave.search.spotlight.schemas.search_result import SpotlightSearchResult

if TYPE_CHECKING:
    from vespa.application import Vespa


class VespaVectorDB:
    """Vespa vector database for spotlight search.

    Compiles SpotlightPlan + embeddings into Vespa YQL and executes queries.
    Uses pyvespa for query execution (synchronous, run in thread pool).

    Features:
    - Query-only (no feed/delete operations)
    - Fail-fast error handling
    - Async via thread pool (pyvespa is synchronous)
    """

    def __init__(
        self,
        app: Vespa,
        logger: ContextualLogger,
        filter_translator: FilterTranslator,
    ) -> None:
        """Initialize the Vespa vector database.

        Args:
            app: Connected pyvespa Vespa application instance.
            logger: Logger for debug/info messages.
            filter_translator: Translator for filter groups.
        """
        self._app = app
        self._logger = logger
        self._filter_translator = filter_translator

    @classmethod
    async def create(cls, ctx: ApiContext) -> VespaVectorDB:
        """Create and connect to Vespa.

        Uses settings.VESPA_URL and settings.VESPA_PORT for connection.

        Args:
            ctx: API context for logging.

        Returns:
            Connected VespaVectorDB instance.

        Raises:
            RuntimeError: If connection fails.
        """
        from vespa.application import Vespa

        vespa_url = settings.VESPA_URL
        vespa_port = settings.VESPA_PORT

        try:
            app = Vespa(url=vespa_url, port=vespa_port)
        except Exception as e:
            raise RuntimeError(
                f"Failed to connect to Vespa at {vespa_url}:{vespa_port}: {e}"
            ) from e

        ctx.logger.debug(f"[VespaVectorDB] Connected to Vespa at {vespa_url}:{vespa_port}")

        filter_translator = FilterTranslator(logger=ctx.logger)

        return cls(app=app, logger=ctx.logger, filter_translator=filter_translator)

    # =========================================================================
    # Public Interface
    # =========================================================================

    async def compile_query(
        self,
        plan: SpotlightPlan,
        embeddings: SpotlightQueryEmbeddings,
        collection_id: str,
    ) -> str:
        """Compile plan and embeddings into Vespa query.

        Args:
            plan: Search plan with query, filters, strategy, pagination.
            embeddings: Dense and sparse embeddings for the queries.
            collection_id: Collection readable ID for tenant filtering.

        Returns:
            JSON string: {"yql": "...", "params": {...}}

        Raises:
            FilterTranslationError: If filters reference non-filterable fields.
        """
        yql = self._build_yql(plan, collection_id)
        params = self._build_params(plan, embeddings)

        compiled = {"yql": yql, "params": params}

        self._logger.debug(
            f"[VespaVectorDB] Compiled query: YQL={len(yql)} chars, params={len(params)} keys"
        )

        return json.dumps(compiled)

    async def execute_query(
        self,
        compiled_query: str,
    ) -> list[SpotlightSearchResult]:
        """Execute compiled query against Vespa.

        Runs the query in a thread pool since pyvespa is synchronous.

        Args:
            compiled_query: JSON string from compile_query().

        Returns:
            List of search results, ordered by relevance.

        Raises:
            RuntimeError: If query execution fails.
        """
        raise NotImplementedError("execute_query not yet implemented")

    async def close(self) -> None:
        """Close the Vespa connection.

        Note: pyvespa doesn't require explicit cleanup, but we implement
        this for interface compliance and future-proofing.
        """
        self._logger.debug("[VespaVectorDB] Connection closed")
        self._app = None  # type: ignore[assignment]

    # =========================================================================
    # YQL Building
    # =========================================================================

    def _build_yql(self, plan: SpotlightPlan, collection_id: str) -> str:
        """Build the complete YQL query string.

        Args:
            plan: Search plan with query, filters, strategy.
            collection_id: Collection ID for tenant filtering.

        Returns:
            Complete YQL query string.
        """
        # Build retrieval clause based on strategy
        num_embeddings = self._count_dense_embeddings(plan)
        retrieval_clause = self._build_retrieval_clause(plan.retrieval_strategy, num_embeddings)

        # Build WHERE clause parts
        where_parts = [
            # Collection filter (multi-tenant)
            f"airweave_system_metadata_collection_id contains '{collection_id}'",
            # Retrieval clause (nearestNeighbor and/or userInput)
            f"({retrieval_clause})",
        ]

        # Add LLM-generated filters if present
        filter_yql = self._filter_translator.translate(plan.filter_groups)
        if filter_yql:
            where_parts.append(f"({filter_yql})")

        # Build complete YQL
        all_schemas = ", ".join(ALL_VESPA_SCHEMAS)
        yql = f"select * from sources {all_schemas} where {' AND '.join(where_parts)}"

        return yql

    def _build_retrieval_clause(
        self,
        strategy: SpotlightRetrievalStrategy,
        num_embeddings: int,
    ) -> str:
        """Build the retrieval clause based on strategy.

        Args:
            strategy: Retrieval strategy (SEMANTIC, KEYWORD, HYBRID).
            num_embeddings: Number of dense embeddings (primary + variations).

        Returns:
            YQL retrieval clause.
        """
        # Build nearestNeighbor operators for each embedding (semantic search)
        nn_parts = []
        for i in range(num_embeddings):
            nn_parts.append(
                f'({{label:"q{i}", targetHits:{TARGET_HITS}, '
                f'"hnsw.exploreAdditionalHits":{HNSW_EXPLORE_ADDITIONAL}}}'
                f"nearestNeighbor(dense_embedding, q{i}))"
            )
        nn_clause = " OR ".join(nn_parts) if nn_parts else ""

        # BM25 text search clause (keyword search)
        bm25_clause = f"{{targetHits:{TARGET_HITS}}}userInput(@query)"

        if strategy == SpotlightRetrievalStrategy.SEMANTIC:
            return nn_clause
        elif strategy == SpotlightRetrievalStrategy.KEYWORD:
            return bm25_clause
        else:
            # HYBRID: combine both
            if nn_clause:
                return f"({bm25_clause}) OR {nn_clause}"
            return bm25_clause

    def _count_dense_embeddings(self, plan: SpotlightPlan) -> int:
        """Count how many dense embeddings will be generated.

        Args:
            plan: Search plan with query.

        Returns:
            Number of dense embeddings (1 for primary + len(variations)).
        """
        return 1 + len(plan.query.variations)

    # =========================================================================
    # Params Building
    # =========================================================================

    def _build_params(
        self,
        plan: SpotlightPlan,
        embeddings: SpotlightQueryEmbeddings,
    ) -> Dict[str, Any]:
        """Build Vespa query parameters.

        Args:
            plan: Search plan with limit, offset, strategy.
            embeddings: Query embeddings (dense and sparse).

        Returns:
            Dict of Vespa query parameters.
        """
        # Calculate effective rerank count (must cover offset + limit)
        effective_rerank = plan.limit + plan.offset
        global_phase_rerank = max(DEFAULT_GLOBAL_PHASE_RERANK_COUNT, effective_rerank)

        # Ranking profile name matches strategy value directly (semantic, keyword, hybrid)
        params: Dict[str, Any] = {
            "query": plan.query.primary,
            "ranking.profile": plan.retrieval_strategy.value,
            "hits": plan.limit,
            "offset": plan.offset,
            "presentation.summary": "full",
            "ranking.softtimeout.enable": "false",
            "ranking.globalPhase.rerankCount": global_phase_rerank,
        }

        # Add dense embeddings (for semantic/hybrid search only)
        if embeddings.dense_embeddings and plan.retrieval_strategy in (
            SpotlightRetrievalStrategy.SEMANTIC,
            SpotlightRetrievalStrategy.HYBRID,
        ):
            # Embedding for each query (multi-query nearestNeighbor)
            for i, dense_emb in enumerate(embeddings.dense_embeddings):
                params[f"input.query(q{i})"] = {"values": dense_emb.vector}

        # Add sparse embedding (for keyword/hybrid search)
        if embeddings.sparse_embedding and plan.retrieval_strategy in (
            SpotlightRetrievalStrategy.KEYWORD,
            SpotlightRetrievalStrategy.HYBRID,
        ):
            sparse_tensor = self._convert_sparse_to_tensor(embeddings.sparse_embedding)
            if sparse_tensor:
                params["input.query(q_sparse)"] = sparse_tensor

        return params

    def _convert_sparse_to_tensor(
        self, sparse_emb: SpotlightSparseEmbedding
    ) -> Optional[Dict[str, Any]]:
        """Convert SpotlightSparseEmbedding to Vespa tensor format.

        Args:
            sparse_emb: Sparse embedding with indices and values.

        Returns:
            Vespa tensor format: {"cells": {"token_id": weight, ...}}
        """
        if not sparse_emb.indices or not sparse_emb.values:
            return None

        # Build cells as object format: {"token_id": weight, ...}
        cells = {}
        for idx, val in zip(sparse_emb.indices, sparse_emb.values, strict=False):
            cells[str(idx)] = float(val)

        return {"cells": cells}
