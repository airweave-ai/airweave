"""YQL Builder for agentic search.

Converts SearchPlan + QueryEmbeddings into a complete Vespa YQL query and parameters.
This is the bridge between the planner's output and Vespa execution.
"""

from typing import Any, Dict, Optional

from airweave.api.context import ApiContext
from airweave.platform.destinations.vespa.config import (
    ALL_VESPA_SCHEMAS,
    HNSW_EXPLORE_ADDITIONAL,
    TARGET_HITS,
)
from airweave.search.agentic_search.builder.filter_translator import FilterGroupTranslator
from airweave.search.agentic_search.builder.schemas import VespaQuery
from airweave.search.agentic_search.openai import QueryEmbeddings
from airweave.search.agentic_search.planner.schemas import RetrievalStrategy, SearchPlan


class AgenticQueryBuilder:
    """Builds Vespa YQL queries from SearchPlan and QueryEmbeddings.

    Takes the planner's SearchPlan and embedder's QueryEmbeddings and produces:
    1. A complete YQL query string
    2. Query parameters (embeddings, pagination, ranking profile)

    Usage:
        builder = AgenticQueryBuilder(ctx=ctx)
        yql, params = builder.build(plan, embeddings, collection_id)
    """

    def __init__(self, ctx: Optional[ApiContext] = None) -> None:
        """Initialize the builder.

        Args:
            ctx: API context for logging (optional)
        """
        self._ctx = ctx
        self._filter_translator = FilterGroupTranslator(ctx=ctx)

    def _log(self, message: str, level: str = "debug") -> None:
        """Log a message if context is available."""
        if self._ctx:
            logger = getattr(self._ctx.logger, level)
            logger(f"[AgenticQueryBuilder] {message}")

    def build(
        self,
        plan: SearchPlan,
        embeddings: QueryEmbeddings,
        collection_id: str,
    ) -> VespaQuery:
        """Build VespaQuery from search plan.

        Args:
            plan: SearchPlan from the planner
            embeddings: QueryEmbeddings from the embedder
            collection_id: Collection's readable ID for tenant filtering

        Returns:
            VespaQuery ready for execution
        """
        strategy = plan.retrieval_strategy.value
        self._log(f"Building YQL for {len(plan.queries)} queries, strategy={strategy}")

        # Build YQL
        yql = self._build_yql(plan, collection_id)

        # Build params
        params = self._build_params(plan, embeddings)

        self._log(f"Built YQL ({len(yql)} chars) with {len(params)} params")

        return VespaQuery(yql=yql, params=params)

    def _build_yql(self, plan: SearchPlan, collection_id: str) -> str:
        """Build the complete YQL query string.

        Args:
            plan: SearchPlan with queries, filters, strategy
            collection_id: Collection ID for tenant filtering

        Returns:
            Complete YQL query string
        """
        # Build retrieval clause based on strategy
        retrieval_clause = self._build_retrieval_clause(plan.queries, plan.retrieval_strategy)

        # Build WHERE clause parts
        where_parts = [
            # Collection filter (multi-tenant)
            f"airweave_system_metadata_collection_id contains '{collection_id}'",
            # Retrieval clause (nearestNeighbor and/or userInput)
            f"({retrieval_clause})",
        ]

        # Add user filters if present
        filter_yql = self._filter_translator.translate(plan.filter_groups)
        if filter_yql:
            where_parts.append(f"({filter_yql})")

        # Build complete YQL
        all_schemas = ", ".join(ALL_VESPA_SCHEMAS)
        yql = f"select * from sources {all_schemas} where {' AND '.join(where_parts)}"

        return yql

    def _build_retrieval_clause(
        self,
        queries: list[str],
        strategy: RetrievalStrategy,
    ) -> str:
        """Build the retrieval clause based on strategy.

        Args:
            queries: List of search queries
            strategy: Retrieval strategy (SEMANTIC, KEYWORD, HYBRID)

        Returns:
            YQL retrieval clause
        """
        # Build nearestNeighbor operators for each query (semantic search)
        nn_parts = []
        for i in range(len(queries)):
            nn_parts.append(
                f'({{label:"q{i}", targetHits:{TARGET_HITS}, '
                f'"hnsw.exploreAdditionalHits":{HNSW_EXPLORE_ADDITIONAL}}}'
                f"nearestNeighbor(dense_embedding, q{i}))"
            )
        nn_clause = " OR ".join(nn_parts)

        # BM25 text search clause (keyword search)
        bm25_clause = f"{{targetHits:{TARGET_HITS}}}userInput(@query)"

        if strategy == RetrievalStrategy.SEMANTIC:
            return nn_clause
        elif strategy == RetrievalStrategy.KEYWORD:
            return bm25_clause
        else:
            # HYBRID: combine both
            return f"({bm25_clause}) OR {nn_clause}"

    def _build_params(
        self,
        plan: SearchPlan,
        embeddings: QueryEmbeddings,
    ) -> Dict[str, Any]:
        """Build Vespa query parameters.

        Args:
            plan: SearchPlan with limit, offset, strategy
            embeddings: QueryEmbeddings with dense and sparse embeddings

        Returns:
            Dict of Vespa query parameters
        """
        primary_query = plan.queries[0] if plan.queries else ""

        # Calculate effective rerank count (must cover offset + limit)
        effective_rerank = plan.limit + plan.offset
        global_phase_rerank = max(100, effective_rerank)

        # Select ranking profile based on strategy
        ranking_profile = self._get_ranking_profile(plan.retrieval_strategy)

        params: Dict[str, Any] = {
            "query": primary_query,
            "ranking.profile": ranking_profile,
            "hits": plan.limit,
            "offset": plan.offset,
            "presentation.summary": "full",
            "ranking.softtimeout.enable": "false",
            "ranking.globalPhase.rerankCount": global_phase_rerank,
        }

        # Add dense embeddings (for semantic/hybrid search)
        if embeddings.dense:
            # Primary embedding for ranking
            params["ranking.features.query(query_embedding)"] = {"values": embeddings.dense[0]}
            # Embedding for each query (multi-query nearestNeighbor)
            for i, dense_emb in enumerate(embeddings.dense):
                params[f"input.query(q{i})"] = {"values": dense_emb}

        # Add sparse embedding (for keyword/hybrid search)
        if embeddings.sparse and plan.retrieval_strategy in (
            RetrievalStrategy.KEYWORD,
            RetrievalStrategy.HYBRID,
        ):
            sparse_tensor = self._convert_sparse_to_tensor(embeddings.sparse)
            if sparse_tensor:
                params["input.query(q_sparse)"] = sparse_tensor

        return params

    def _get_ranking_profile(self, strategy: RetrievalStrategy) -> str:
        """Get the Vespa ranking profile for the retrieval strategy.

        Args:
            strategy: Retrieval strategy

        Returns:
            Vespa ranking profile name
        """
        if strategy == RetrievalStrategy.SEMANTIC:
            return "semantic-only"
        elif strategy == RetrievalStrategy.KEYWORD:
            return "keyword-only"
        else:
            return "hybrid-rrf"

    def _convert_sparse_to_tensor(self, sparse_emb: Any) -> Optional[Dict[str, Any]]:
        """Convert FastEmbed sparse embedding to Vespa tensor format.

        Args:
            sparse_emb: FastEmbed SparseEmbedding with indices and values

        Returns:
            Vespa tensor format: {"cells": {"token_id": weight, ...}}
        """
        try:
            if hasattr(sparse_emb, "indices") and hasattr(sparse_emb, "values"):
                indices = sparse_emb.indices
                values = sparse_emb.values
            elif isinstance(sparse_emb, dict):
                indices = sparse_emb.get("indices", [])
                values = sparse_emb.get("values", [])
            else:
                self._log(f"Unknown sparse embedding type: {type(sparse_emb)}", level="warning")
                return None

            # Convert numpy arrays to Python lists if needed
            if hasattr(indices, "tolist"):
                indices = indices.tolist()
            if hasattr(values, "tolist"):
                values = values.tolist()

            if not indices or not values:
                return None

            # Build cells as object format: {"token_id": weight, ...}
            cells = {}
            for idx, val in zip(indices, values, strict=False):
                cells[str(idx)] = float(val)

            return {"cells": cells}

        except Exception as e:
            self._log(f"Failed to convert sparse embedding: {e}", level="warning")
            return None
