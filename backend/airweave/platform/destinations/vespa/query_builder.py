"""Query builder - constructs YQL queries and parameters for Vespa search.

Pure transformation logic with no I/O dependencies.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from airweave.platform.destinations.vespa.config import (
    ALL_VESPA_SCHEMAS,
    HNSW_EXPLORE_ADDITIONAL,
    TARGET_HITS,
)
from airweave.platform.destinations.vespa.filter_translator import FilterTranslator


class QueryBuilder:
    """Builds YQL queries and parameters for Vespa search.

    This class encapsulates all the logic for constructing Vespa queries,
    including:
    - YQL WHERE clause construction
    - nearestNeighbor operators for vector search
    - BM25 text search via userInput
    - Multi-query expansion support
    - Filter injection
    """

    def __init__(self, filter_translator: Optional[FilterTranslator] = None):
        """Initialize the query builder.

        Args:
            filter_translator: Optional FilterTranslator for filter conversion.
                              If not provided, a default instance is created.
        """
        self._filter_translator = filter_translator or FilterTranslator()

    def build_yql(
        self,
        queries: List[str],
        collection_id: UUID,
        filter: Optional[Dict[str, Any]] = None,
        retrieval_strategy: str = "hybrid",
    ) -> str:
        """Build complete YQL query string based on retrieval strategy.

        Constructs a YQL query that combines:
        - Collection-based filtering (multi-tenant)
        - BM25 text search via userInput (keyword/hybrid)
        - Vector search via nearestNeighbor (neural/hybrid)
        - Optional user-provided filters

        Args:
            queries: List of search query texts (primary + expanded)
            collection_id: SQL collection UUID for tenant filtering
            filter: Optional Qdrant-style filter dict
            retrieval_strategy: Search strategy - "hybrid", "neural", or "keyword"

        Returns:
            Complete YQL query string
        """
        # Translate filter to YQL
        yql_filter = self._filter_translator.translate(filter)

        # Build retrieval clause based on strategy
        retrieval_clause = self._build_retrieval_clause(queries, retrieval_strategy)

        # Base WHERE clause with collection filter and retrieval
        where_parts = [
            f"airweave_system_metadata_collection_id contains '{collection_id}'",
            f"({retrieval_clause})",
        ]

        # Inject user filter if present
        if yql_filter:
            where_parts.append(f"({yql_filter})")

        # Query all entity schemas
        all_schemas = ", ".join(ALL_VESPA_SCHEMAS)
        yql = f"select * from sources {all_schemas} where {' AND '.join(where_parts)}"
        return yql

    def _build_retrieval_clause(self, queries: List[str], strategy: str) -> str:
        """Build the retrieval clause based on strategy.

        Args:
            queries: List of search queries
            strategy: "hybrid", "neural", or "keyword"

        Returns:
            YQL retrieval clause
        """
        # Build nearestNeighbor operators for neural/hybrid
        nn_parts = []
        for i in range(len(queries)):
            nn_parts.append(
                f'({{label:"q{i}", targetHits:{TARGET_HITS}, '
                f'"hnsw.exploreAdditionalHits":{HNSW_EXPLORE_ADDITIONAL}}}'
                f"nearestNeighbor(dense_embedding, q{i}))"
            )
        nn_clause = " OR ".join(nn_parts)

        # BM25 text search clause
        bm25_clause = f"{{targetHits:{TARGET_HITS}}}userInput(@query)"

        if strategy == "neural":
            # Pure vector search only
            return nn_clause
        elif strategy == "keyword":
            # Pure BM25 text search only
            return bm25_clause
        else:
            # Default: hybrid - combine both
            return f"({bm25_clause}) OR {nn_clause}"

    def build_params(
        self,
        queries: List[str],
        limit: int,
        offset: int,
        dense_embeddings: Optional[List[List[float]]],
        sparse_embeddings: Optional[List[Any]] = None,
        retrieval_strategy: str = "hybrid",
    ) -> Dict[str, Any]:
        """Build Vespa query parameters with pre-computed embeddings.

        Creates embedding parameters for each query (q0, q1, q2, ...) to support
        multiple nearestNeighbor operators in the YQL.

        Args:
            queries: List of search query texts
            limit: Maximum number of results
            offset: Results to skip (pagination) - passed to Vespa for server-side pagination
            dense_embeddings: Pre-computed 3072-dim embeddings (one per query), None for keyword
            sparse_embeddings: Pre-computed FastEmbed sparse embeddings for keyword scoring
            retrieval_strategy: Search strategy - "hybrid", "neural", or "keyword"

        Returns:
            Dict of Vespa query parameters
        """
        primary_query = queries[0] if queries else ""

        # Calculate effective rerank counts (must cover offset + limit for proper ranking)
        effective_rerank = limit + offset
        global_phase_rerank = max(100, effective_rerank)

        # Select ranking profile based on retrieval strategy
        ranking_profile = self._get_ranking_profile(retrieval_strategy)

        query_params: Dict[str, Any] = {
            "query": primary_query,
            "ranking.profile": ranking_profile,
            # Server-side pagination: Vespa applies offset/hits after ranking
            "hits": limit,
            "offset": offset,
            # Note: We don't specify presentation.summary - Vespa's default summary includes
            # ALL fields with "summary" indexing, including fields from child schemas (e.g., url)
            # Timeout: increase from default 500ms to prevent soft doom during setup
            # Soft timeout: enable graceful degradation with partial results
            # See: https://docs.vespa.ai/en/performance/graceful-degradation.html
            "timeout": "10s",
            "ranking.softtimeout.enable": "true",
            # Rerank count must be >= offset + limit to ensure correct pagination
            "ranking.globalPhase.rerankCount": global_phase_rerank,
        }

        # Add dense embeddings (for neural/hybrid search)
        if dense_embeddings:
            # Primary embedding for ranking
            query_params["ranking.features.query(query_embedding)"] = {
                "values": dense_embeddings[0]
            }

            # Add embedding for each query for multi-query nearestNeighbor
            for i, dense_emb in enumerate(dense_embeddings):
                query_params[f"input.query(q{i})"] = {"values": dense_emb}

        # Add sparse embedding for keyword scoring (for keyword/hybrid search)
        if sparse_embeddings and retrieval_strategy in ("keyword", "hybrid"):
            sparse_tensor = self._convert_sparse_query_to_tensor(sparse_embeddings[0])
            if sparse_tensor:
                query_params["input.query(q_sparse)"] = sparse_tensor

        return query_params

    def _convert_sparse_query_to_tensor(self, sparse_emb: Any) -> Optional[Dict[str, Any]]:
        """Convert FastEmbed sparse embedding to Vespa query tensor format.

        Args:
            sparse_emb: FastEmbed SparseEmbedding with indices and values

        Returns:
            Vespa tensor format: {"cells": {"token_id": weight, ...}}
            Note: Uses object format (not array) to match Vespa's mapped tensor expectations
        """
        try:
            if hasattr(sparse_emb, "indices") and hasattr(sparse_emb, "values"):
                indices = sparse_emb.indices
                values = sparse_emb.values
            elif isinstance(sparse_emb, dict):
                indices = sparse_emb.get("indices", [])
                values = sparse_emb.get("values", [])
            else:
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
        except Exception:
            return None

    def _get_ranking_profile(self, retrieval_strategy: str) -> str:
        """Get the Vespa ranking profile for the retrieval strategy.

        Args:
            retrieval_strategy: "hybrid", "neural", or "keyword"

        Returns:
            Vespa ranking profile name
        """
        # Map "neural" to "semantic" profile (Vespa uses "semantic" profile name)
        if retrieval_strategy == "neural":
            return "semantic"
        # Other strategies (keyword, hybrid) map directly
        return retrieval_strategy

    def escape_query(self, query: str) -> str:
        """Escape a query string for safe inclusion in YQL.

        Args:
            query: Raw query string

        Returns:
            Escaped query string safe for YQL
        """
        return query.replace("\\", "\\\\").replace('"', '\\"')

    @property
    def filter_translator(self) -> FilterTranslator:
        """Access the filter translator for direct filter translation."""
        return self._filter_translator
