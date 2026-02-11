"""Vespa vector database client for agentic search.

Handles query compilation (plan + embeddings → YQL) and execution.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.search.agentic_search.external.vector_database.vespa.config import (
    ALL_VESPA_SCHEMAS,
    DEFAULT_GLOBAL_PHASE_RERANK_COUNT,
    HNSW_EXPLORE_ADDITIONAL,
    TARGET_HITS,
)
from airweave.search.agentic_search.external.vector_database.vespa.filter_translator import (
    FilterTranslator,
)
from airweave.search.agentic_search.schemas.compiled_query import AgenticSearchCompiledQuery
from airweave.search.agentic_search.schemas.plan import AgenticSearchPlan
from airweave.search.agentic_search.schemas.query_embeddings import (
    AgenticSearchQueryEmbeddings,
    AgenticSearchSparseEmbedding,
)
from airweave.search.agentic_search.schemas.retrieval_strategy import AgenticSearchRetrievalStrategy
from airweave.search.agentic_search.schemas.search_result import (
    AgenticSearchAccessControl,
    AgenticSearchBreadcrumb,
    AgenticSearchResult,
    AgenticSearchResults,
    AgenticSearchSystemMetadata,
)

if TYPE_CHECKING:
    from vespa.application import Vespa


class VespaVectorDB:
    """Vespa vector database for agentic search.

    Compiles AgenticSearchPlan + embeddings into Vespa YQL and executes queries.
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
        plan: AgenticSearchPlan,
        embeddings: AgenticSearchQueryEmbeddings,
        collection_id: str,
    ) -> AgenticSearchCompiledQuery:
        """Compile plan and embeddings into Vespa query.

        Args:
            plan: Search plan with query, filters, strategy, pagination.
            embeddings: Dense and sparse embeddings for the queries.
            collection_id: Collection readable ID for tenant filtering.

        Returns:
            AgenticSearchCompiledQuery with raw (full) and display (no embeddings) versions.

        Raises:
            FilterTranslationError: If filters reference non-filterable fields.
        """
        yql = self._build_yql(plan, collection_id)
        params = self._build_params(plan, embeddings)

        # Raw query for execution (includes embeddings)
        raw_query = {"yql": yql, "params": params}

        # Display params: exclude embedding vectors (they can be huge)
        display_params = {k: v for k, v in params.items() if not k.startswith("input.query(")}
        display_query = f"YQL:\n{yql}\n\nParams:\n{json.dumps(display_params, indent=2)}"

        # Log summary
        self._logger.debug(
            f"[VespaVectorDB] Compiled query: YQL={len(yql)} chars, params={len(params)} keys"
        )
        self._logger.debug(f"[VespaVectorDB] YQL:\n{yql}")
        self._logger.debug(f"[VespaVectorDB] Params (no embeddings): {display_params}")

        return AgenticSearchCompiledQuery(
            vector_db="vespa",
            display=display_query,
            raw=raw_query,
        )

    async def execute_query(
        self,
        compiled_query: AgenticSearchCompiledQuery,
    ) -> AgenticSearchResults:
        """Execute compiled query against Vespa.

        Runs the query in a thread pool since pyvespa is synchronous.

        Args:
            compiled_query: AgenticSearchCompiledQuery from compile_query().

        Returns:
            Search results container, ordered by relevance.

        Raises:
            RuntimeError: If query execution fails.
        """
        # Extract raw query (includes embeddings)
        raw = compiled_query.raw
        yql = raw["yql"]
        params = raw["params"]

        # Merge YQL into params (pyvespa expects all in one dict)
        query_params = {**params, "yql": yql}

        # Execute query in thread pool (pyvespa is synchronous)
        start_time = time.monotonic()
        try:
            response = await asyncio.to_thread(self._app.query, body=query_params)
        except Exception as e:
            self._logger.error(f"[VespaVectorDB] Query execution failed: {e}")
            raise RuntimeError(f"Vespa query failed: {e}") from e
        query_time_ms = (time.monotonic() - start_time) * 1000

        # Check for errors
        if not response.is_successful():
            error_msg = getattr(response, "json", {}).get("error", str(response))
            self._logger.error(f"[VespaVectorDB] Vespa returned error: {error_msg}")
            raise RuntimeError(f"Vespa query error: {error_msg}")

        # Extract metrics
        raw_json = response.json if hasattr(response, "json") else {}
        root = raw_json.get("root", {})
        coverage = root.get("coverage", {})
        total_count = root.get("fields", {}).get("totalCount", 0)
        hits = response.hits or []

        self._logger.debug(
            f"[VespaVectorDB] Query completed in {query_time_ms:.1f}ms, "
            f"total={total_count}, hits={len(hits)}, "
            f"coverage={coverage.get('coverage', 100.0):.1f}%"
        )

        # Convert hits to results
        return self._convert_hits_to_results(hits)

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

    def _build_yql(self, plan: AgenticSearchPlan, collection_id: str) -> str:
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
            # Collection filter (multi-tenant) - use contains with single quotes
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
        strategy: AgenticSearchRetrievalStrategy,
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

        if strategy == AgenticSearchRetrievalStrategy.SEMANTIC:
            return nn_clause
        elif strategy == AgenticSearchRetrievalStrategy.KEYWORD:
            return bm25_clause
        else:
            # HYBRID: combine both
            if nn_clause:
                return f"({bm25_clause}) OR {nn_clause}"
            return bm25_clause

    def _count_dense_embeddings(self, plan: AgenticSearchPlan) -> int:
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
        plan: AgenticSearchPlan,
        embeddings: AgenticSearchQueryEmbeddings,
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
        # Note: We don't specify presentation.summary - Vespa's default summary includes
        # ALL fields with "summary" indexing, including fields from child schemas (like url)
        params: Dict[str, Any] = {
            "query": plan.query.primary,
            "ranking.profile": plan.retrieval_strategy.value,
            "hits": plan.limit,
            "offset": plan.offset,
            "ranking.softtimeout.enable": "false",
            "ranking.globalPhase.rerankCount": global_phase_rerank,
        }

        # Add dense embeddings (for semantic/hybrid search only)
        if embeddings.dense_embeddings and plan.retrieval_strategy in (
            AgenticSearchRetrievalStrategy.SEMANTIC,
            AgenticSearchRetrievalStrategy.HYBRID,
        ):
            # Embedding for each query (multi-query nearestNeighbor)
            for i, dense_emb in enumerate(embeddings.dense_embeddings):
                params[f"input.query(q{i})"] = {"values": dense_emb.vector}

        # Add sparse embedding (for keyword/hybrid search)
        if embeddings.sparse_embedding and plan.retrieval_strategy in (
            AgenticSearchRetrievalStrategy.KEYWORD,
            AgenticSearchRetrievalStrategy.HYBRID,
        ):
            sparse_tensor = self._convert_sparse_to_tensor(embeddings.sparse_embedding)
            if sparse_tensor:
                params["input.query(q_sparse)"] = sparse_tensor

        return params

    def _convert_sparse_to_tensor(
        self, sparse_emb: AgenticSearchSparseEmbedding
    ) -> Optional[Dict[str, Any]]:
        """Convert AgenticSearchSparseEmbedding to Vespa tensor format.

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

    # =========================================================================
    # Hit Conversion
    # =========================================================================

    def _convert_hits_to_results(self, hits: List[Dict[str, Any]]) -> AgenticSearchResults:
        """Convert Vespa hits to AgenticSearchResults container.

        Args:
            hits: List of Vespa hit dictionaries.

        Returns:
            AgenticSearchResults container with results ordered by relevance.
        """
        results: list[AgenticSearchResult] = []
        for i, hit in enumerate(hits):
            fields = hit.get("fields", {})
            relevance = hit.get("relevance", 0.0)

            # Log debug info for first few hits
            if i < 5:
                self._log_hit_debug(i, fields, relevance)

            # Validate required fields
            entity_id = fields.get("entity_id")
            if not entity_id:
                self._logger.warning(f"[VespaVectorDB] Skipping hit {i}: missing entity_id")
                continue

            # Parse payload for raw_source_fields (contains web_url and other source-specific data)
            raw_source_fields = self._parse_payload(fields.get("payload"))

            result = AgenticSearchResult(
                entity_id=entity_id,
                name=self._get_required_field(fields, "name", entity_id),
                relevance_score=relevance,
                breadcrumbs=self._extract_breadcrumbs(fields.get("breadcrumbs", [])),
                created_at=self._parse_timestamp(fields.get("created_at")),
                updated_at=self._parse_timestamp(fields.get("updated_at")),
                textual_representation=self._get_required_field(
                    fields, "textual_representation", entity_id
                ),
                airweave_system_metadata=self._extract_system_metadata(fields, entity_id),
                access=self._extract_access_control(fields),
                web_url=self._get_required_field(raw_source_fields, "web_url", entity_id),
                url=fields.get("url"),  # Only present for FileEntity (download link)
                raw_source_fields=raw_source_fields,
            )
            results.append(result)

        return AgenticSearchResults(results=results)

    def _get_required_field(self, fields: Dict[str, Any], field_name: str, entity_id: str) -> str:
        """Get a required field, logging warning if missing."""
        value = fields.get(field_name)
        if not value:
            self._logger.warning(
                f"[VespaVectorDB] Entity {entity_id}: missing required field '{field_name}'"
            )
            return ""
        return str(value)

    def _log_hit_debug(self, index: int, fields: Dict[str, Any], relevance: float) -> None:
        """Log debug info for a hit."""
        entity_name = fields.get("name", "N/A")
        entity_type = fields.get("airweave_system_metadata_entity_type", "N/A")
        truncated_name = entity_name[:40] if entity_name else "N/A"
        self._logger.debug(
            f"[VespaVectorDB] Hit {index}: name='{truncated_name}' "
            f"type={entity_type} relevance={relevance:.4f}"
        )

    def _extract_system_metadata(
        self, fields: Dict[str, Any], entity_id: str
    ) -> AgenticSearchSystemMetadata:
        """Extract system metadata from flattened Vespa fields.

        Logs warnings for missing required metadata fields.
        """
        source_name = fields.get("airweave_system_metadata_source_name")
        entity_type = fields.get("airweave_system_metadata_entity_type")

        if not source_name:
            self._logger.warning(
                f"[VespaVectorDB] Entity {entity_id}: missing source_name in metadata"
            )
        if not entity_type:
            self._logger.warning(
                f"[VespaVectorDB] Entity {entity_id}: missing entity_type in metadata"
            )

        return AgenticSearchSystemMetadata(
            source_name=source_name or "",
            entity_type=entity_type or "",
            sync_id=fields.get("airweave_system_metadata_sync_id") or "",
            sync_job_id=fields.get("airweave_system_metadata_sync_job_id") or "",
            chunk_index=fields.get("airweave_system_metadata_chunk_index") or 0,
            original_entity_id=fields.get("airweave_system_metadata_original_entity_id") or "",
        )

    def _extract_access_control(self, fields: Dict[str, Any]) -> AgenticSearchAccessControl:
        """Extract access control from flattened Vespa fields."""
        return AgenticSearchAccessControl(
            is_public=fields.get("access_is_public"),
            viewers=fields.get("access_viewers"),
        )

    def _extract_breadcrumbs(self, raw_breadcrumbs: List[Any]) -> List[AgenticSearchBreadcrumb]:
        """Extract breadcrumbs from Vespa list of dicts."""
        breadcrumbs = []
        for bc in raw_breadcrumbs:
            if isinstance(bc, dict):
                breadcrumbs.append(
                    AgenticSearchBreadcrumb(
                        entity_id=bc.get("entity_id", ""),
                        name=bc.get("name", ""),
                        entity_type=bc.get("entity_type", ""),
                    )
                )
        return breadcrumbs

    def _parse_timestamp(self, epoch_value: Any) -> Optional[datetime]:
        """Convert epoch timestamp to datetime.

        Vespa stores timestamps as epoch seconds. This returns a datetime
        object which Pydantic will serialize to ISO format.
        """
        if not epoch_value:
            return None
        try:
            return datetime.fromtimestamp(epoch_value)
        except (ValueError, TypeError, OSError):
            return None

    def _parse_payload(self, payload_str: Any) -> Dict[str, Any]:
        """Parse payload JSON string into raw_source_fields dict."""
        if not payload_str or not isinstance(payload_str, str):
            return {}
        try:
            return json.loads(payload_str)
        except json.JSONDecodeError:
            return {}
