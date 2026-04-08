"""Search plan executor — shared pipeline for all search tiers.

Merge filters -> embed query -> compile DB query -> execute -> SearchResults.
When federated sources exist, also searches them with plan.query.primary,
applies filters in-memory, and merges results using Reciprocal Rank Fusion.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.domains.search.adapters.vector_db.protocol import VectorDBProtocol
from airweave.domains.search.builders.search_plan import SearchPlanBuilder
from airweave.domains.search.exceptions import FederatedSearchError
from airweave.domains.search.protocols import SearchPlanExecutorProtocol
from airweave.domains.search.types import (
    FilterGroup,
    QueryEmbeddings,
    RetrievalStrategy,
    SearchPlan,
    SearchResults,
)
from airweave.domains.search.types.filters import FilterableField, FilterCondition, FilterOperator
from airweave.domains.search.types.results import (
    SearchAccessControl,
    SearchBreadcrumb,
    SearchResult,
    SearchSystemMetadata,
)
from airweave.domains.source_connections.protocols import SourceConnectionRepositoryProtocol
from airweave.domains.sources.exceptions import SourceAuthError, SourceCreationError
from airweave.domains.sources.protocols import (
    SourceLifecycleServiceProtocol,
    SourceRegistryProtocol,
)
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sources._base import BaseSource

# RRF constant (standard value used in hybrid search systems)
RRF_K = 60


class SearchPlanExecutor(SearchPlanExecutorProtocol):
    """Executes a search plan against the vector database and federated sources.

    Pipeline:
    1. Merge plan filters with user-supplied filters
    2. Discover federated sources for the collection
    3. Adjust limit/offset for RRF pagination (if federated sources exist)
    4. Embed query and execute vector search
    5. Search federated sources with plan.query.primary
    6. Apply filters in-memory to federated results
    7. Merge via RRF and paginate
    """

    def __init__(
        self,
        dense_embedder: DenseEmbedderProtocol,
        sparse_embedder: SparseEmbedderProtocol,
        vector_db: VectorDBProtocol,
        sc_repo: SourceConnectionRepositoryProtocol,
        source_registry: SourceRegistryProtocol,
        source_lifecycle: SourceLifecycleServiceProtocol,
    ) -> None:
        """Initialize with embedders, vector database, and federated source dependencies."""
        self._dense_embedder = dense_embedder
        self._sparse_embedder = sparse_embedder
        self._vector_db = vector_db
        self._sc_repo = sc_repo
        self._source_registry = source_registry
        self._source_lifecycle = source_lifecycle

    async def execute(
        self,
        plan: SearchPlan,
        user_filter: list[FilterGroup],
        collection_id: str,
        db: AsyncSession,
        ctx: ApiContext,
        collection_readable_id: str,
    ) -> SearchResults:
        """Execute the full search pipeline including federated sources."""
        # 1. Merge plan filters with user filters
        complete_plan = SearchPlanBuilder.build(plan, user_filter)

        # 2. Discover federated sources for this collection
        federated_sources = await self._discover_federated_sources(db, ctx, collection_readable_id)

        # 3. Adjust limit/offset for RRF pagination (if federated sources exist)
        original_limit = complete_plan.limit
        original_offset = complete_plan.offset
        if federated_sources:
            complete_plan = complete_plan.model_copy(
                update={
                    "limit": original_offset + original_limit,
                    "offset": 0,
                }
            )

        # 4. Run vector DB search and federated search in parallel
        fetch_limit = original_offset + original_limit

        vector_task = asyncio.create_task(self._execute_vector_search(complete_plan, collection_id))

        fed_task = None
        if federated_sources:
            fed_task = asyncio.create_task(
                self._search_federated_sources(
                    federated_sources,
                    plan.query.primary,
                    limit=fetch_limit,
                    ctx=ctx,
                )
            )

        vector_results = await vector_task
        fed_results = await fed_task if fed_task else []

        # 5. If no federated sources, vector DB already has correct limit/offset
        if not federated_sources:
            return SearchResults(results=vector_results)

        # 6. We over-fetched from vector DB (limit=offset+limit, offset=0) for RRF.
        #    Filter federated results in-memory and merge, or slice vector-only.
        fed_filtered = self._apply_filters_in_memory(fed_results, complete_plan.filter_groups)

        if fed_filtered:
            merged = self._merge_with_rrf(vector_results, fed_filtered)
            return SearchResults(results=merged[original_offset : original_offset + original_limit])

        # All federated results filtered out — slice vector results to original window
        return SearchResults(
            results=vector_results[original_offset : original_offset + original_limit]
        )

    async def _execute_vector_search(
        self,
        plan: SearchPlan,
        collection_id: str,
    ) -> list[SearchResult]:
        """Embed, compile, and execute vector DB search.

        Adapter exceptions (EmbedderError, VectorDBError) propagate directly
        to the caller — no wrapping needed since adapters own their error types.
        """
        dense_embeddings = None
        sparse_embedding = None

        if plan.retrieval_strategy in (
            RetrievalStrategy.SEMANTIC,
            RetrievalStrategy.HYBRID,
        ):
            texts = [plan.query.primary] + list(plan.query.variations)
            dense_embeddings = await self._dense_embedder.embed_many(texts)

        if plan.retrieval_strategy in (
            RetrievalStrategy.KEYWORD,
            RetrievalStrategy.HYBRID,
        ):
            sparse_embedding = await self._sparse_embedder.embed(plan.query.primary)

        embeddings = QueryEmbeddings(
            dense_embeddings=dense_embeddings,
            sparse_embedding=sparse_embedding,
        )

        compiled_query = await self._vector_db.compile_query(
            plan=plan,
            embeddings=embeddings,
            collection_id=collection_id,
        )
        return (await self._vector_db.execute_query(compiled_query)).results

    # ------------------------------------------------------------------
    # Federated source discovery
    # ------------------------------------------------------------------

    async def _discover_federated_sources(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        collection_readable_id: str,
    ) -> list[BaseSource]:
        """Discover and instantiate federated sources for a collection.

        Queries source connections, checks the registry for federated_search flag,
        and instantiates via SourceLifecycleService.
        """
        source_connections = await self._sc_repo.get_by_collection_ids(
            db,
            organization_id=ctx.organization.id,
            readable_collection_ids=[collection_readable_id],
        )

        if not source_connections:
            return []

        federated_sources: list[BaseSource] = []
        for sc in source_connections:
            entry = self._source_registry.get(sc.short_name)
            if not entry.federated_search:
                continue

            try:
                source_instance = await self._source_lifecycle.create(
                    db=db,
                    source_connection_id=UUID(str(sc.id)),
                    ctx=ctx,
                )
                federated_sources.append(source_instance)
            except (SourceAuthError, SourceCreationError, NotFoundException):
                # Auth/config errors are user errors — let them propagate
                # directly so the service layer can handle them without
                # emitting SearchFailedEvent.
                raise
            except Exception as e:
                raise FederatedSearchError([(sc.short_name, e)]) from e

        return federated_sources

    # ------------------------------------------------------------------
    # Federated search execution
    # ------------------------------------------------------------------

    async def _search_federated_sources(
        self,
        sources: list[BaseSource],
        query: str,
        limit: int,
        ctx: ApiContext,
    ) -> list[SearchResult]:
        """Search all federated sources concurrently and return deduplicated results.

        Raises FederatedSearchError if any source fails.
        """
        results_lists = await asyncio.gather(
            *[self._search_single_source(source, query, limit, ctx) for source in sources],
            return_exceptions=True,
        )

        # Check for failures — fail if any source errored
        source_errors: list[tuple[str, BaseException]] = []
        for idx, result_or_exc in enumerate(results_lists):
            if isinstance(result_or_exc, BaseException):
                source_name = sources[idx].__class__.__name__
                source_errors.append((source_name, result_or_exc))

        if source_errors:
            raise FederatedSearchError(source_errors)

        # All succeeded — deduplicate and return
        seen_ids: set[str] = set()
        all_results: list[SearchResult] = []

        for result_list in results_lists:
            for result in result_list:  # type: ignore[union-attr]
                if result.entity_id not in seen_ids:
                    seen_ids.add(result.entity_id)
                    all_results.append(result)

        return all_results

    _FEDERATED_MAX_RETRIES = 2
    _FEDERATED_INITIAL_DELAY = 1.0

    async def _search_single_source(
        self,
        source: BaseSource,
        query: str,
        limit: int,
        ctx: ApiContext,
    ) -> list[SearchResult]:
        """Search a single federated source with retries on transient errors."""
        source_name = source.__class__.__name__
        ctx.logger.debug(f"[FederatedSearch] Searching {source_name} with query: '{query}'")

        last_error: Exception | None = None
        delay = self._FEDERATED_INITIAL_DELAY

        for attempt in range(self._FEDERATED_MAX_RETRIES + 1):
            try:
                entities = await source.search(query, limit=limit)  # type: ignore[misc]
                ctx.logger.debug(
                    f"[FederatedSearch] {source_name} returned {len(entities)} results"  # type: ignore[arg-type]
                )
                break
            except Exception as e:
                last_error = e
                status = getattr(e, "status_code", None)
                is_transient = isinstance(status, int) and status in {429, 500, 502, 503, 504}
                if not is_transient or attempt == self._FEDERATED_MAX_RETRIES:
                    raise
                ctx.logger.warning(
                    f"[FederatedSearch] {source_name} transient error "
                    f"(attempt {attempt + 1}/{self._FEDERATED_MAX_RETRIES + 1}): {e}"
                )
                await asyncio.sleep(delay)
                delay *= 2.0
        else:
            raise last_error  # type: ignore[misc]

        # Get source short_name from the source's metadata
        short_name = getattr(source, "short_name", source_name.lower())

        return [
            self._entity_to_search_result(entity, short_name)
            for entity in entities  # type: ignore[attr-defined]
        ]

    # ------------------------------------------------------------------
    # Entity conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _entity_to_search_result(entity: BaseEntity, source_short_name: str) -> SearchResult:
        """Convert a BaseEntity from a federated source to SearchResult.

        Maps entity fields to the unified SearchResult format used by vector DB results.
        """
        original_entity_id = str(entity.entity_id)
        entity_id = f"{original_entity_id}__chunk_0"
        sys_meta = entity.airweave_system_metadata
        assert sys_meta is not None, f"Entity {original_entity_id} missing airweave_system_metadata"

        # Build breadcrumbs from entity breadcrumbs
        assert entity.breadcrumbs is not None, f"Entity {original_entity_id} missing breadcrumbs"
        breadcrumbs = [
            SearchBreadcrumb(
                entity_id=str(bc.entity_id),
                name=bc.name,
                entity_type=bc.entity_type,
            )
            for bc in entity.breadcrumbs
        ]

        # Access control (access is genuinely optional — not all sources set it)
        access = SearchAccessControl(
            is_public=entity.access.is_public if entity.access else None,
            viewers=entity.access.viewers if entity.access else None,
        )

        # Source-specific fields = full payload minus BaseEntity fields
        payload = entity.model_dump(mode="json", exclude_none=True)
        base_fields = set(BaseEntity.model_fields.keys())
        source_fields = {k: v for k, v in payload.items() if k not in base_fields}

        # web_url is a computed field on some entities (e.g., SlackMessageEntity),
        # not on BaseEntity — read from serialized payload
        web_url = payload.get("web_url", "")

        assert entity.name is not None, f"Entity {original_entity_id} missing name"
        assert entity.textual_representation is not None, (
            f"Entity {original_entity_id} missing textual_representation"
        )

        return SearchResult(
            entity_id=entity_id,
            name=entity.name,
            relevance_score=0.0,  # Replaced by RRF score
            breadcrumbs=breadcrumbs,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            textual_representation=entity.textual_representation,
            airweave_system_metadata=SearchSystemMetadata(
                source_name=sys_meta.source_name or source_short_name,
                entity_type=sys_meta.entity_type or entity.__class__.__name__,
                sync_id=None,
                sync_job_id=None,
                chunk_index=0,
                original_entity_id=original_entity_id,
            ),
            access=access,
            web_url=web_url,
            url=None,
            raw_source_fields=source_fields,
        )

    # ------------------------------------------------------------------
    # In-memory filtering
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_filters_in_memory(
        results: list[SearchResult],
        filter_groups: list[FilterGroup],
    ) -> list[SearchResult]:
        """Apply filter groups to results in-memory.

        Same semantics as Vespa: AND within a group, OR across groups.
        If no filter groups, all results pass.
        """
        if not filter_groups:
            return results

        return [r for r in results if _matches_any_group(r, filter_groups)]

    # ------------------------------------------------------------------
    # RRF merge
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_with_rrf(
        vector_results: list[SearchResult],
        federated_results: list[SearchResult],
        k: int = RRF_K,
    ) -> list[SearchResult]:
        """Merge vector and federated results using Reciprocal Rank Fusion.

        RRF formula: score(d) = Σ 1 / (k + rank + 1) for each list containing d.
        """
        if not federated_results:
            return vector_results
        if not vector_results:
            return federated_results

        scores: dict[str, float] = {}
        result_map: dict[str, SearchResult] = {}

        for rank, r in enumerate(vector_results):
            scores[r.entity_id] = scores.get(r.entity_id, 0) + 1 / (k + rank + 1)
            result_map[r.entity_id] = r

        for rank, r in enumerate(federated_results):
            scores[r.entity_id] = scores.get(r.entity_id, 0) + 1 / (k + rank + 1)
            result_map[r.entity_id] = r

        sorted_ids = sorted(scores, key=lambda eid: scores[eid], reverse=True)

        return [
            result_map[eid].model_copy(update={"relevance_score": scores[eid]})
            for eid in sorted_ids
        ]


# ── In-memory filter helpers (module-level for testability) ──────────


def _get_field_value(result: SearchResult, field: FilterableField) -> Any:
    """Extract the value of a filterable field from a SearchResult.

    Resolves the dot-notation path from FilterableField.value (e.g.,
    "airweave_system_metadata.source_name") by traversing the object tree.
    If a list is encountered mid-path (e.g., breadcrumbs), returns a list
    of values from each element (any-match semantics).
    """
    parts = field.value.split(".")
    obj: Any = result

    for part in parts:
        if obj is None:
            return None
        if isinstance(obj, list):
            # List field (e.g., breadcrumbs) — collect attribute from each element
            return [getattr(item, part, None) for item in obj]
        obj = getattr(obj, part, None)

    return obj


def _evaluate_condition(value: Any, condition: FilterCondition) -> bool:
    """Evaluate a single filter condition against a value.

    For list values (breadcrumbs), returns True if ANY element matches.
    """
    op = condition.operator
    target = condition.value

    # Handle list values (breadcrumb fields) — any-match semantics
    if isinstance(value, list):
        return any(_evaluate_scalar(v, op, target) for v in value)

    return _evaluate_scalar(value, op, target)


def _evaluate_scalar(value: Any, op: FilterOperator, target: Any) -> bool:  # noqa: C901
    """Evaluate a scalar comparison."""
    if value is None:
        # None fails all comparisons except not_equals and not_in
        return op in (FilterOperator.NOT_EQUALS, FilterOperator.NOT_IN)

    # Try datetime comparison for ordering ops (string comparison breaks
    # because str(datetime) uses space separator while ISO uses 'T')
    cmp_value: Any = value
    cmp_target: Any = target
    if op in (
        FilterOperator.GREATER_THAN,
        FilterOperator.LESS_THAN,
        FilterOperator.GREATER_THAN_OR_EQUAL,
        FilterOperator.LESS_THAN_OR_EQUAL,
    ):
        parsed = _try_parse_datetimes(value, target)
        if parsed:
            cmp_value, cmp_target = parsed
        else:
            cmp_value, cmp_target = str(value), str(target)
    else:
        cmp_value, cmp_target = str(value), str(target)

    sv = str(value)

    if op == FilterOperator.EQUALS:
        return sv == str(target)
    if op == FilterOperator.NOT_EQUALS:
        return sv != str(target)
    if op == FilterOperator.CONTAINS:
        return str(target).lower() in sv.lower()
    if op == FilterOperator.IN:
        return sv in [str(t) for t in target] if isinstance(target, list) else False
    if op == FilterOperator.NOT_IN:
        return sv not in [str(t) for t in target] if isinstance(target, list) else True
    if op == FilterOperator.GREATER_THAN:
        return cmp_value > cmp_target
    if op == FilterOperator.LESS_THAN:
        return cmp_value < cmp_target
    if op == FilterOperator.GREATER_THAN_OR_EQUAL:
        return cmp_value >= cmp_target
    if op == FilterOperator.LESS_THAN_OR_EQUAL:
        return cmp_value <= cmp_target

    return False


def _try_parse_datetimes(value: Any, target: Any) -> tuple["datetime", "datetime"] | None:
    """Try to parse both value and target as datetimes for comparison.

    Returns a (datetime, datetime) tuple if both parse successfully, None otherwise.
    """

    def _parse(v: Any) -> datetime | None:
        if isinstance(v, datetime):
            return v
        s = str(v).strip("'\"")
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(s)
            # Make naive for comparison if needed
            return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
        except (ValueError, AttributeError):
            return None

    pv = _parse(value)
    pt = _parse(target)
    if pv is not None and pt is not None:
        return (pv, pt)
    return None


def _matches_group(result: SearchResult, group: FilterGroup) -> bool:
    """Check if a result matches ALL conditions in a group (AND semantics)."""
    for condition in group.conditions:
        value = _get_field_value(result, condition.field)
        if not _evaluate_condition(value, condition):
            return False
    return True


def _matches_any_group(result: SearchResult, groups: list[FilterGroup]) -> bool:
    """Check if a result matches ANY group (OR semantics)."""
    return any(_matches_group(result, group) for group in groups)
