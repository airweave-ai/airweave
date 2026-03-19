"""Vespa vector database client for search.

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
from airweave.domains.embedders.types import SparseEmbedding
from airweave.domains.search.adapters.vector_db.exceptions import VectorDBError
from airweave.domains.search.adapters.vector_db.filter_translator import FilterTranslator
from airweave.domains.search.adapters.vector_db.vespa_config import (
    ALL_VESPA_SCHEMAS,
    DEFAULT_GLOBAL_PHASE_RERANK_COUNT,
    HNSW_EXPLORE_ADDITIONAL,
    TARGET_HITS,
)
from airweave.domains.search.types.embeddings import QueryEmbeddings
from airweave.domains.search.types.plan import RetrievalStrategy, SearchPlan
from airweave.domains.search.types.results import (
    CompiledQuery,
    SearchAccessControl,
    SearchBreadcrumb,
    SearchResult,
    SearchResults,
    SearchSystemMetadata,
)

if TYPE_CHECKING:
    from vespa.application import Vespa


class VespaVectorDB:
    """Vespa vector database for search.

    Compiles SearchPlan + embeddings into Vespa YQL and executes queries.
    Uses pyvespa for query execution (synchronous, run in thread pool).
    """

    def __init__(
        self,
        app: Vespa,
        logger: ContextualLogger,
        filter_translator: FilterTranslator,
    ) -> None:
        """Initialize the Vespa vector database."""
        self._app = app
        self._logger = logger
        self._filter_translator = filter_translator

    @classmethod
    async def create(cls, ctx: ApiContext) -> VespaVectorDB:
        """Create and connect to Vespa."""
        from vespa.application import Vespa

        vespa_url = settings.VESPA_URL
        vespa_port = settings.VESPA_PORT

        try:
            app = Vespa(url=vespa_url, port=vespa_port)
        except Exception as e:
            raise VectorDBError(
                f"Failed to connect to Vespa at {vespa_url}:{vespa_port}: {e}",
                cause=e,
            ) from e

        ctx.logger.debug(f"[VespaVectorDB] Connected to Vespa at {vespa_url}:{vespa_port}")

        filter_translator = FilterTranslator(logger=ctx.logger)

        return cls(app=app, logger=ctx.logger, filter_translator=filter_translator)

    # =========================================================================
    # Public Interface
    # =========================================================================

    async def compile_query(
        self,
        plan: SearchPlan,
        embeddings: QueryEmbeddings,
        collection_id: str,
    ) -> CompiledQuery:
        """Compile plan and embeddings into Vespa query."""
        yql = self._build_yql(plan, collection_id)
        params = self._build_params(plan, embeddings)

        raw_query = {"yql": yql, "params": params}

        display_params = {k: v for k, v in params.items() if not k.startswith("input.query(")}
        display_query = f"YQL:\n{yql}\n\nParams:\n{json.dumps(display_params, indent=2)}"

        self._logger.debug(
            f"[VespaVectorDB] Compiled query: YQL={len(yql)} chars, params={len(params)} keys"
        )

        return CompiledQuery(
            vector_db="vespa",
            display=display_query,
            raw=raw_query,
        )

    async def execute_query(
        self,
        compiled_query: CompiledQuery,
    ) -> SearchResults:
        """Execute compiled query against Vespa."""
        raw = compiled_query.raw
        yql = raw["yql"]
        params = raw["params"]

        query_params = {**params, "yql": yql}

        start_time = time.monotonic()
        try:
            response = await asyncio.to_thread(self._app.query, body=query_params)
        except Exception as e:
            # Vespa rejects queries that produce no parseable terms (e.g. "." or pure
            # punctuation with BM25/keyword). Return empty results instead of crashing.
            error_str = str(e)
            if "NullItem" in error_str or "Invalid query parameter" in error_str:
                self._logger.warning(
                    f"[VespaVectorDB] Query not parseable by Vespa, returning empty: {e}"
                )
                return SearchResults(results=[])
            self._logger.error(f"[VespaVectorDB] Query execution failed: {e}")
            raise VectorDBError(f"Vespa query failed: {e}", cause=e) from e
        query_time_ms = (time.monotonic() - start_time) * 1000

        if not response.is_successful():
            error_msg = getattr(response, "json", {}).get("error", str(response))
            self._logger.error(f"[VespaVectorDB] Vespa returned error: {error_msg}")
            raise VectorDBError(f"Vespa query error: {error_msg}")

        raw_json = response.json if hasattr(response, "json") else {}
        root = raw_json.get("root", {})
        coverage = root.get("coverage", {})
        total_count = root.get("fields", {}).get("totalCount", 0)
        hits = response.hits or []

        coverage_pct = coverage.get("coverage", 100.0)

        self._logger.debug(
            f"[VespaVectorDB] Query completed in {query_time_ms:.1f}ms, "
            f"total={total_count}, hits={len(hits)}, "
            f"coverage={coverage_pct:.1f}%"
        )

        return self._convert_hits_to_results(hits)

    async def count(
        self,
        filter_groups: list,
        collection_id: str,
    ) -> int:
        """Count entities matching filters without retrieving content."""
        where_parts = [
            f"airweave_system_metadata_collection_id contains '{collection_id}'",
        ]

        filter_yql = self._filter_translator.translate(filter_groups)
        if filter_yql:
            where_parts.append(f"({filter_yql})")

        all_schemas = ", ".join(ALL_VESPA_SCHEMAS)
        yql = f"select * from sources {all_schemas} where {' AND '.join(where_parts)}"

        query_params = {"yql": yql, "hits": 0}

        try:
            response = await asyncio.to_thread(self._app.query, body=query_params)
        except Exception as e:
            self._logger.error(f"[VespaVectorDB] Count query failed: {e}")
            raise VectorDBError(f"Vespa count query failed: {e}", cause=e) from e

        if not response.is_successful():
            error_msg = getattr(response, "json", {}).get("error", str(response))
            raise VectorDBError(f"Vespa count query error: {error_msg}")

        raw_json = response.json if hasattr(response, "json") else {}
        total_count = raw_json.get("root", {}).get("fields", {}).get("totalCount", 0)

        self._logger.debug(f"[VespaVectorDB] Count query: {total_count} matches")
        return total_count

    async def filter_search(
        self,
        filter_groups: list,
        collection_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list:
        """Retrieve entities matching filters without embeddings or ranking."""
        where_parts = [
            f"airweave_system_metadata_collection_id contains '{collection_id}'",
        ]

        filter_yql = self._filter_translator.translate(filter_groups)
        if filter_yql:
            where_parts.append(f"({filter_yql})")

        all_schemas = ", ".join(ALL_VESPA_SCHEMAS)
        yql = f"select * from sources {all_schemas} where {' AND '.join(where_parts)}"

        try:
            response = await asyncio.to_thread(
                self._app.query, body={"yql": yql, "hits": limit, "offset": offset}
            )
        except Exception as e:
            self._logger.error(f"[VespaVectorDB] Filter search failed: {e}")
            raise VectorDBError(f"Vespa filter search failed: {e}", cause=e) from e

        if not response.is_successful():
            error_msg = getattr(response, "json", {}).get("error", str(response))
            raise VectorDBError(f"Vespa filter search error: {error_msg}")

        hits = response.hits or []
        self._logger.debug(f"[VespaVectorDB] Filter search: {len(hits)} hits")

        results = self._convert_hits_to_results(hits)
        return results.results

    async def close(self) -> None:
        """Close the Vespa connection."""
        self._logger.debug("[VespaVectorDB] Connection closed")
        self._app = None  # type: ignore[assignment]

    # =========================================================================
    # YQL Building
    # =========================================================================

    def _build_yql(self, plan: SearchPlan, collection_id: str) -> str:
        """Build the complete YQL query string."""
        num_embeddings = self._count_dense_embeddings(plan)
        retrieval_clause = self._build_retrieval_clause(plan.retrieval_strategy, num_embeddings)

        where_parts = [
            f"airweave_system_metadata_collection_id contains '{collection_id}'",
            f"({retrieval_clause})",
        ]

        filter_yql = self._filter_translator.translate(plan.filter_groups)
        if filter_yql:
            where_parts.append(f"({filter_yql})")

        all_schemas = ", ".join(ALL_VESPA_SCHEMAS)
        yql = f"select * from sources {all_schemas} where {' AND '.join(where_parts)}"

        return yql

    def _build_retrieval_clause(
        self,
        strategy: RetrievalStrategy,
        num_embeddings: int,
    ) -> str:
        """Build the retrieval clause based on strategy."""
        nn_parts = []
        for i in range(num_embeddings):
            nn_parts.append(
                f'({{label:"q{i}", targetHits:{TARGET_HITS}, '
                f'"hnsw.exploreAdditionalHits":{HNSW_EXPLORE_ADDITIONAL}}}'
                f"nearestNeighbor(dense_embedding, q{i}))"
            )
        nn_clause = " OR ".join(nn_parts) if nn_parts else ""

        bm25_clause = f"{{targetHits:{TARGET_HITS}}}userInput(@query)"

        if strategy == RetrievalStrategy.SEMANTIC:
            return nn_clause
        elif strategy == RetrievalStrategy.KEYWORD:
            return bm25_clause
        else:
            # HYBRID: combine both
            if nn_clause:
                return f"({bm25_clause}) OR {nn_clause}"
            return bm25_clause

    def _count_dense_embeddings(self, plan: SearchPlan) -> int:
        """Count how many dense embeddings will be generated."""
        return 1 + len(plan.query.variations)

    # =========================================================================
    # Params Building
    # =========================================================================

    def _build_params(
        self,
        plan: SearchPlan,
        embeddings: QueryEmbeddings,
    ) -> Dict[str, Any]:
        """Build Vespa query parameters."""
        effective_rerank = plan.limit + plan.offset
        global_phase_rerank = max(DEFAULT_GLOBAL_PHASE_RERANK_COUNT, effective_rerank)

        params: Dict[str, Any] = {
            "query": plan.query.primary,
            "ranking.profile": plan.retrieval_strategy.value,
            "hits": plan.limit,
            "offset": plan.offset,
            "ranking.softtimeout.enable": "true",
            "timeout": "15s",
            "ranking.globalPhase.rerankCount": global_phase_rerank,
        }

        if embeddings.dense_embeddings and plan.retrieval_strategy in (
            RetrievalStrategy.SEMANTIC,
            RetrievalStrategy.HYBRID,
        ):
            for i, dense_emb in enumerate(embeddings.dense_embeddings):
                params[f"input.query(q{i})"] = {"values": dense_emb.vector}

        if embeddings.sparse_embedding and plan.retrieval_strategy in (
            RetrievalStrategy.KEYWORD,
            RetrievalStrategy.HYBRID,
        ):
            sparse_tensor = self._convert_sparse_to_tensor(embeddings.sparse_embedding)
            if sparse_tensor:
                params["input.query(q_sparse)"] = sparse_tensor
                num_tokens = len(sparse_tensor.get("cells", {}))
                self._logger.debug(f"[VespaVectorDB] Sparse embedding: {num_tokens} tokens")
            else:
                self._logger.warning("[VespaVectorDB] Sparse embedding conversion returned None")
        elif plan.retrieval_strategy in (
            RetrievalStrategy.KEYWORD,
            RetrievalStrategy.HYBRID,
        ):
            self._logger.warning(
                f"[VespaVectorDB] No sparse embedding for {plan.retrieval_strategy.value} query"
            )

        has_dense = any(
            k.startswith("input.query(q") and k != "input.query(q_sparse)" for k in params
        )
        has_sparse = "input.query(q_sparse)" in params
        self._logger.debug(
            f"[VespaVectorDB] Query params: dense={has_dense}, sparse={has_sparse}, "
            f"profile={params.get('ranking.profile')}, "
            f"rerankCount={global_phase_rerank}"
        )

        return params

    def _convert_sparse_to_tensor(
        self, sparse_emb: SparseEmbedding
    ) -> Optional[Dict[str, Dict[str, float]]]:
        """Convert SparseEmbedding to Vespa tensor format."""
        if not sparse_emb.indices or not sparse_emb.values:
            return None

        cells = {}
        for idx, val in zip(sparse_emb.indices, sparse_emb.values, strict=False):
            cells[str(idx)] = float(val)

        return {"cells": cells}

    # =========================================================================
    # Hit Conversion
    # =========================================================================

    def _convert_hits_to_results(self, hits: List[Dict[str, Any]]) -> SearchResults:
        """Convert Vespa hits to SearchResults container."""
        results: list[SearchResult] = []
        for i, hit in enumerate(hits):
            fields = hit.get("fields", {})
            relevance = hit.get("relevance", 0.0)

            entity_id = fields.get("entity_id")
            if not entity_id:
                self._logger.warning(f"[VespaVectorDB] Skipping hit {i}: missing entity_id")
                continue

            raw_source_fields = self._parse_payload(fields.get("payload"))

            result = SearchResult(
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
                url=fields.get("url"),
                raw_source_fields=raw_source_fields,
            )
            results.append(result)

        return SearchResults(results=results)

    def _get_required_field(self, fields: Dict[str, Any], field_name: str, entity_id: str) -> str:
        """Get a required field, logging warning if missing."""
        value = fields.get(field_name)
        if not value:
            self._logger.warning(
                f"[VespaVectorDB] Entity {entity_id}: missing required field '{field_name}'"
            )
            return ""
        return str(value)

    def _extract_system_metadata(
        self, fields: Dict[str, Any], entity_id: str
    ) -> SearchSystemMetadata:
        """Extract system metadata from flattened Vespa fields."""
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

        return SearchSystemMetadata(
            source_name=source_name or "",
            entity_type=entity_type or "",
            sync_id=fields.get("airweave_system_metadata_sync_id") or "",
            sync_job_id=fields.get("airweave_system_metadata_sync_job_id") or "",
            chunk_index=fields.get("airweave_system_metadata_chunk_index") or 0,
            original_entity_id=fields.get("airweave_system_metadata_original_entity_id") or "",
        )

    def _extract_access_control(self, fields: Dict[str, Any]) -> SearchAccessControl:
        """Extract access control from flattened Vespa fields."""
        return SearchAccessControl(
            is_public=fields.get("access_is_public"),
            viewers=fields.get("access_viewers"),
        )

    def _extract_breadcrumbs(self, raw_breadcrumbs: List[Any]) -> List[SearchBreadcrumb]:
        """Extract breadcrumbs from Vespa list of dicts."""
        breadcrumbs = []
        for bc in raw_breadcrumbs:
            if isinstance(bc, dict):
                breadcrumbs.append(
                    SearchBreadcrumb(
                        entity_id=bc.get("entity_id", ""),
                        name=bc.get("name", ""),
                        entity_type=bc.get("entity_type", ""),
                    )
                )
        return breadcrumbs

    def _parse_timestamp(self, epoch_value: Any) -> Optional[datetime]:
        """Convert epoch timestamp to datetime."""
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
