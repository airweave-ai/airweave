"""Tests for SearchPlanExecutor — vector search, federated search, filtering, RRF merge.

Covers:
- Vector-only search (no federated sources)
- Federated-only search (vector returns nothing)
- Mixed search with RRF merge
- In-memory filtering of federated results
- Pagination (offset + limit) with RRF
- Edge cases: auth failures, all filtered out, empty collections
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from airweave.domains.embedders.fakes.embedder import FakeDenseEmbedder, FakeSparseEmbedder
from airweave.domains.search.adapters.vector_db.fakes.vector_db import FakeVectorDB
from airweave.domains.search.executor import (
    SearchPlanExecutor,
    _evaluate_scalar,
    _get_field_value,
    _matches_any_group,
    _matches_group,
)
from airweave.domains.search.types import SearchPlan, SearchQuery, SearchResults
from airweave.domains.search.types.filters import (
    FilterableField,
    FilterCondition,
    FilterGroup,
    FilterOperator,
)
from airweave.domains.search.types.results import (
    SearchAccessControl,
    SearchBreadcrumb,
    SearchResult,
    SearchSystemMetadata,
)
from airweave.domains.source_connections.fakes.repository import FakeSourceConnectionRepository
from airweave.domains.sources.fakes.lifecycle import FakeSourceLifecycleService
from airweave.domains.sources.fakes.registry import FakeSourceRegistry
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.platform.configs._base import Fields
from airweave.platform.entities._base import AirweaveSystemMetadata, BaseEntity, Breadcrumb
from airweave.platform.entities.slack import SlackMessageEntity

# ── Helpers ──────────────────────────────────────────────────────────


def _make_search_result(
    entity_id: str = "ent-1__chunk_0",
    name: str = "Test Entity",
    score: float = 0.9,
    source_name: str = "github",
    entity_type: str = "GitHubIssueEntity",
    sync_id: str | None = None,
    sync_job_id: str | None = None,
    chunk_index: int = 0,
    original_entity_id: str | None = None,
    content: str = "Some content",
    breadcrumbs: list[SearchBreadcrumb] | None = None,
    created_at: datetime | None = None,
) -> SearchResult:
    """Build a SearchResult with sensible defaults."""
    return SearchResult(
        entity_id=entity_id,
        name=name,
        relevance_score=score,
        breadcrumbs=breadcrumbs
        or [SearchBreadcrumb(entity_id="parent-1", name="Parent", entity_type="FolderEntity")],
        textual_representation=content,
        airweave_system_metadata=SearchSystemMetadata(
            source_name=source_name,
            entity_type=entity_type,
            sync_id=sync_id or str(uuid4()),
            sync_job_id=sync_job_id or str(uuid4()),
            chunk_index=chunk_index,
            original_entity_id=original_entity_id or entity_id,
        ),
        access=SearchAccessControl(),
        web_url=f"https://example.com/{entity_id}",
        raw_source_fields={},
        created_at=created_at,
    )


def _make_federated_result(
    entity_id: str = "msg-1__chunk_0",
    name: str = "Slack Message",
    source_name: str = "slack",
    entity_type: str = "SlackMessageEntity",
    content: str = "Hey team, deploy is done",
    breadcrumbs: list[SearchBreadcrumb] | None = None,
    created_at: datetime | None = None,
) -> SearchResult:
    """Build a SearchResult that looks like a federated result (no sync fields)."""
    return SearchResult(
        entity_id=entity_id,
        name=name,
        relevance_score=0.0,
        breadcrumbs=breadcrumbs
        or [SearchBreadcrumb(entity_id="chan-1", name="#general", entity_type="SlackChannel")],
        textual_representation=content,
        airweave_system_metadata=SearchSystemMetadata(
            source_name=source_name,
            entity_type=entity_type,
            sync_id=None,
            sync_job_id=None,
            chunk_index=0,
            original_entity_id=entity_id.replace("__chunk_0", ""),
        ),
        access=SearchAccessControl(),
        web_url=f"https://slack.com/archives/{entity_id}",
        raw_source_fields={"channel_name": "#general"},
        created_at=created_at,
    )


def _make_plan(
    query: str = "deployment issues",
    limit: int = 10,
    offset: int = 0,
    strategy: str = "hybrid",
) -> SearchPlan:
    """Build a SearchPlan with sensible defaults."""
    return SearchPlan(
        query=SearchQuery(primary=query),
        limit=limit,
        offset=offset,
        retrieval_strategy=strategy,
    )


def _make_filter(field: str, operator: str, value) -> FilterGroup:
    """Build a single-condition FilterGroup."""
    return FilterGroup(
        conditions=[
            FilterCondition(field=field, operator=operator, value=value),
        ]
    )


def _make_ctx() -> MagicMock:
    """Build a minimal ApiContext mock."""
    ctx = MagicMock()
    ctx.organization.id = uuid4()
    ctx.request_id = str(uuid4())
    ctx.logger = MagicMock()
    return ctx


def _make_source_connection(
    short_name: str,
    federated: bool = False,
    readable_collection_id: str = "my-collection",
):
    """Build a mock source connection."""
    sc = MagicMock()
    sc.short_name = short_name
    sc.id = uuid4()
    sc.connection_id = uuid4()
    sc.sync_id = None if federated else uuid4()
    sc.readable_collection_id = readable_collection_id
    return sc


def _make_registry_entry(short_name: str, federated: bool = False) -> SourceRegistryEntry:
    """Build a minimal SourceRegistryEntry."""
    return SourceRegistryEntry(
        short_name=short_name,
        name=short_name.title(),
        description=f"{short_name} source",
        class_name=f"{short_name.title()}Source",
        source_class_ref=MagicMock,
        config_ref=None,
        auth_config_ref=None,
        auth_fields=Fields(fields=[]),
        config_fields=Fields(fields=[]),
        supported_auth_providers=[],
        runtime_auth_all_fields=[],
        runtime_auth_optional_fields=set(),
        auth_methods=None,
        oauth_type=None,
        requires_byoc=False,
        supports_continuous=False,
        federated_search=federated,
        supports_temporal_relevance=True,
        supports_access_control=False,
        rate_limit_level=None,
        feature_flag=None,
        labels=None,
        output_entity_definitions=[],
    )


class _FakeFederatedSource:
    """Minimal fake source that returns entities from search()."""

    short_name = "slack"

    def __init__(self, entities: list[BaseEntity] | None = None):
        self.entities = entities or []
        self.search_calls: list[tuple] = []

    async def search(self, query: str, limit: int) -> list[BaseEntity]:
        self.search_calls.append((query, limit))
        return self.entities


def _make_slack_entity(
    entity_id: str = "msg-1",
    text: str = "deploy completed",
    channel_name: str = "general",
) -> SlackMessageEntity:
    """Build a SlackMessageEntity as federated search would return it."""
    entity = SlackMessageEntity(
        entity_id=entity_id,
        name=text[:50],
        breadcrumbs=[
            Breadcrumb(entity_id="chan-1", name=f"#{channel_name}", entity_type="SlackChannel")
        ],
        created_at=datetime(2026, 3, 15, 10, 0, 0),
        textual_representation=f"Message in #{channel_name}: {text}",
        airweave_system_metadata=AirweaveSystemMetadata(
            source_name="slack",
            entity_type="SlackMessageEntity",
        ),
        # SlackMessageEntity required fields
        text=text,
        ts=entity_id,
        channel_id="chan-1",
        channel_name=channel_name,
        message_time=datetime(2026, 3, 15, 10, 0, 0),
        permalink=f"https://workspace.slack.com/archives/chan-1/p{entity_id}",
        web_url_value=f"https://workspace.slack.com/archives/chan-1/p{entity_id}",
    )
    return entity


def _build_executor(
    vector_db: FakeVectorDB | None = None,
    sc_repo: FakeSourceConnectionRepository | None = None,
    source_registry: FakeSourceRegistry | None = None,
    source_lifecycle: FakeSourceLifecycleService | None = None,
) -> SearchPlanExecutor:
    """Build a SearchPlanExecutor with fakes for all dependencies."""
    return SearchPlanExecutor(
        dense_embedder=FakeDenseEmbedder(),
        sparse_embedder=FakeSparseEmbedder(),
        vector_db=vector_db or FakeVectorDB(),
        sc_repo=sc_repo or FakeSourceConnectionRepository(),
        source_registry=source_registry or FakeSourceRegistry(),
        source_lifecycle=source_lifecycle or FakeSourceLifecycleService(),
    )


# ═══════════════════════════════════════════════════════════════════════
# RRF MERGE
# ═══════════════════════════════════════════════════════════════════════


class TestMergeWithRRF:
    """Tests for _merge_with_rrf (Reciprocal Rank Fusion)."""

    def test_empty_federated_returns_vector(self):
        v = [_make_search_result(entity_id="v1")]
        assert SearchPlanExecutor._merge_with_rrf(v, []) == v

    def test_empty_vector_returns_federated(self):
        f = [_make_federated_result(entity_id="f1")]
        assert SearchPlanExecutor._merge_with_rrf([], f) == f

    def test_interleaves_by_rank(self):
        """Top results from each list get near-equal RRF scores, interleaving them."""
        v = [_make_search_result(entity_id=f"v{i}") for i in range(3)]
        f = [_make_federated_result(entity_id=f"f{i}") for i in range(3)]

        merged = SearchPlanExecutor._merge_with_rrf(v, f, k=60)

        assert len(merged) == 6
        # Rank 1 from each list gets score 1/61 — they alternate
        ids = [r.entity_id for r in merged]
        # v0 and f0 tie at 1/61, then v1 and f1 at 1/62, etc.
        # Within ties, vector comes first (processed first)
        assert ids == ["v0", "f0", "v1", "f1", "v2", "f2"]

    def test_rrf_scores_are_set(self):
        v = [_make_search_result(entity_id="v0")]
        f = [_make_federated_result(entity_id="f0")]

        merged = SearchPlanExecutor._merge_with_rrf(v, f, k=60)

        for r in merged:
            assert r.relevance_score == pytest.approx(1 / 61)

    def test_duplicate_entity_gets_boosted(self):
        """If same entity_id appears in both lists, scores are summed."""
        shared_id = "shared-1__chunk_0"
        v = [_make_search_result(entity_id=shared_id)]
        f = [_make_federated_result(entity_id=shared_id)]

        merged = SearchPlanExecutor._merge_with_rrf(v, f, k=60)

        assert len(merged) == 1
        assert merged[0].relevance_score == pytest.approx(2 / 61)


# ═══════════════════════════════════════════════════════════════════════
# IN-MEMORY FILTERING
# ═══════════════════════════════════════════════════════════════════════


class TestGetFieldValue:
    """Tests for _get_field_value — dynamic dot-notation field resolution."""

    def test_top_level_field(self):
        r = _make_search_result(entity_id="ent-1")
        assert _get_field_value(r, FilterableField.ENTITY_ID) == "ent-1"

    def test_nested_field(self):
        r = _make_search_result(source_name="slack")
        assert _get_field_value(r, FilterableField.SYSTEM_METADATA_SOURCE_NAME) == "slack"

    def test_breadcrumb_field_returns_list(self):
        r = _make_search_result(
            breadcrumbs=[
                SearchBreadcrumb(entity_id="p1", name="Engineering", entity_type="Folder"),
                SearchBreadcrumb(entity_id="p2", name="Docs", entity_type="Folder"),
            ]
        )
        assert _get_field_value(r, FilterableField.BREADCRUMBS_NAME) == [
            "Engineering",
            "Docs",
        ]

    def test_none_sync_id_returns_none(self):
        r = _make_federated_result()
        assert _get_field_value(r, FilterableField.SYSTEM_METADATA_SYNC_ID) is None


class TestEvaluateScalar:
    """Tests for _evaluate_scalar — individual operator logic."""

    def test_equals(self):
        assert _evaluate_scalar("slack", FilterOperator.EQUALS, "slack") is True
        assert _evaluate_scalar("github", FilterOperator.EQUALS, "slack") is False

    def test_not_equals(self):
        assert _evaluate_scalar("slack", FilterOperator.NOT_EQUALS, "github") is True
        assert _evaluate_scalar("slack", FilterOperator.NOT_EQUALS, "slack") is False

    def test_contains(self):
        assert _evaluate_scalar("Engineering Team", FilterOperator.CONTAINS, "engineer") is True
        assert _evaluate_scalar("Engineering Team", FilterOperator.CONTAINS, "sales") is False

    def test_in_operator(self):
        assert _evaluate_scalar("slack", FilterOperator.IN, ["slack", "github"]) is True
        assert _evaluate_scalar("notion", FilterOperator.IN, ["slack", "github"]) is False

    def test_not_in_operator(self):
        assert _evaluate_scalar("notion", FilterOperator.NOT_IN, ["slack", "github"]) is True
        assert _evaluate_scalar("slack", FilterOperator.NOT_IN, ["slack", "github"]) is False

    def test_greater_than(self):
        assert _evaluate_scalar("2026-03-15", FilterOperator.GREATER_THAN, "2026-01-01") is True
        assert _evaluate_scalar("2025-01-01", FilterOperator.GREATER_THAN, "2026-01-01") is False

    def test_less_than(self):
        assert _evaluate_scalar("2025-01-01", FilterOperator.LESS_THAN, "2026-01-01") is True

    def test_none_fails_equals(self):
        assert _evaluate_scalar(None, FilterOperator.EQUALS, "something") is False

    def test_none_passes_not_equals(self):
        assert _evaluate_scalar(None, FilterOperator.NOT_EQUALS, "something") is True

    def test_none_passes_not_in(self):
        assert _evaluate_scalar(None, FilterOperator.NOT_IN, ["a", "b"]) is True

    def test_none_fails_in(self):
        assert _evaluate_scalar(None, FilterOperator.IN, ["a", "b"]) is False


class TestMatchesGroup:
    """Tests for _matches_group — AND semantics within a filter group."""

    def test_all_conditions_must_match(self):
        r = _make_search_result(source_name="slack", entity_type="SlackMessageEntity")
        group = FilterGroup(
            conditions=[
                FilterCondition(
                    field="airweave_system_metadata.source_name",
                    operator="equals",
                    value="slack",
                ),
                FilterCondition(
                    field="airweave_system_metadata.entity_type",
                    operator="equals",
                    value="SlackMessageEntity",
                ),
            ]
        )
        assert _matches_group(r, group) is True

    def test_one_failing_condition_rejects(self):
        r = _make_search_result(source_name="github", entity_type="SlackMessageEntity")
        group = FilterGroup(
            conditions=[
                FilterCondition(
                    field="airweave_system_metadata.source_name",
                    operator="equals",
                    value="slack",
                ),
                FilterCondition(
                    field="airweave_system_metadata.entity_type",
                    operator="equals",
                    value="SlackMessageEntity",
                ),
            ]
        )
        assert _matches_group(r, group) is False


class TestMatchesAnyGroup:
    """Tests for _matches_any_group — OR semantics across filter groups."""

    def test_matches_first_group(self):
        r = _make_search_result(source_name="slack")
        groups = [
            _make_filter("airweave_system_metadata.source_name", "equals", "slack"),
            _make_filter("airweave_system_metadata.source_name", "equals", "github"),
        ]
        assert _matches_any_group(r, groups) is True

    def test_matches_second_group(self):
        r = _make_search_result(source_name="github")
        groups = [
            _make_filter("airweave_system_metadata.source_name", "equals", "slack"),
            _make_filter("airweave_system_metadata.source_name", "equals", "github"),
        ]
        assert _matches_any_group(r, groups) is True

    def test_matches_no_group(self):
        r = _make_search_result(source_name="notion")
        groups = [
            _make_filter("airweave_system_metadata.source_name", "equals", "slack"),
            _make_filter("airweave_system_metadata.source_name", "equals", "github"),
        ]
        assert _matches_any_group(r, groups) is False


class TestApplyFiltersInMemory:
    """Tests for SearchPlanExecutor._apply_filters_in_memory."""

    def test_no_filters_passes_all(self):
        results = [_make_federated_result(entity_id=f"f{i}") for i in range(3)]
        filtered = SearchPlanExecutor._apply_filters_in_memory(results, [])
        assert len(filtered) == 3

    def test_source_name_filter_removes_non_matching(self):
        results = [
            _make_federated_result(entity_id="f1", source_name="slack"),
            _make_federated_result(entity_id="f2", source_name="slack"),
        ]
        filters = [_make_filter("airweave_system_metadata.source_name", "equals", "github")]
        filtered = SearchPlanExecutor._apply_filters_in_memory(results, filters)
        assert len(filtered) == 0

    def test_source_name_filter_keeps_matching(self):
        results = [
            _make_federated_result(entity_id="f1", source_name="slack"),
        ]
        filters = [_make_filter("airweave_system_metadata.source_name", "equals", "slack")]
        filtered = SearchPlanExecutor._apply_filters_in_memory(results, filters)
        assert len(filtered) == 1

    def test_entity_type_filter(self):
        slack = _make_federated_result(entity_id="f1", entity_type="SlackMessageEntity")
        github = _make_search_result(entity_id="g1", entity_type="GitHubPREntity")
        filters = [
            _make_filter("airweave_system_metadata.entity_type", "equals", "GitHubPREntity")
        ]
        filtered = SearchPlanExecutor._apply_filters_in_memory([slack, github], filters)
        assert len(filtered) == 1
        assert filtered[0].entity_id == "g1"

    def test_sync_id_filter_excludes_federated(self):
        """Federated results have sync_id=None, so filtering on sync_id excludes them."""
        fed = _make_federated_result(entity_id="f1")
        synced = _make_search_result(entity_id="s1", sync_id="some-sync-id")
        filters = [
            _make_filter("airweave_system_metadata.sync_id", "equals", "some-sync-id")
        ]
        filtered = SearchPlanExecutor._apply_filters_in_memory([fed, synced], filters)
        assert len(filtered) == 1
        assert filtered[0].entity_id == "s1"

    def test_breadcrumb_filter_any_match(self):
        r = _make_federated_result(
            entity_id="f1",
            breadcrumbs=[
                SearchBreadcrumb(entity_id="c1", name="#engineering", entity_type="SlackChannel"),
            ],
        )
        filters = [_make_filter("breadcrumbs.name", "contains", "engineering")]
        filtered = SearchPlanExecutor._apply_filters_in_memory([r], filters)
        assert len(filtered) == 1

    def test_breadcrumb_filter_no_match(self):
        r = _make_federated_result(
            entity_id="f1",
            breadcrumbs=[
                SearchBreadcrumb(entity_id="c1", name="#sales", entity_type="SlackChannel"),
            ],
        )
        filters = [_make_filter("breadcrumbs.name", "contains", "engineering")]
        filtered = SearchPlanExecutor._apply_filters_in_memory([r], filters)
        assert len(filtered) == 0

    def test_or_across_groups(self):
        """Multiple groups are OR'd — result matching any group passes."""
        slack = _make_federated_result(entity_id="f1", source_name="slack")
        github = _make_search_result(entity_id="g1", source_name="github")
        notion = _make_search_result(entity_id="n1", source_name="notion")

        filters = [
            _make_filter("airweave_system_metadata.source_name", "equals", "slack"),
            _make_filter("airweave_system_metadata.source_name", "equals", "github"),
        ]
        filtered = SearchPlanExecutor._apply_filters_in_memory(
            [slack, github, notion], filters
        )
        assert len(filtered) == 2
        assert {r.entity_id for r in filtered} == {"f1", "g1"}

    def test_date_filter(self):
        old = _make_federated_result(
            entity_id="f1", created_at=datetime(2025, 1, 1)
        )
        new = _make_federated_result(
            entity_id="f2", created_at=datetime(2026, 3, 1)
        )
        filters = [_make_filter("created_at", "greater_than", "2026-01-01T00:00:00")]
        filtered = SearchPlanExecutor._apply_filters_in_memory([old, new], filters)
        assert len(filtered) == 1
        assert filtered[0].entity_id == "f2"


# ═══════════════════════════════════════════════════════════════════════
# ENTITY CONVERSION
# ═══════════════════════════════════════════════════════════════════════


class TestEntityToSearchResult:
    """Tests for SearchPlanExecutor._entity_to_search_result."""

    def test_basic_conversion(self):
        entity = _make_slack_entity(entity_id="msg-42", text="deploy done")
        result = SearchPlanExecutor._entity_to_search_result(entity, "slack")

        assert result.entity_id == "msg-42__chunk_0"
        assert result.name == "deploy done"
        assert result.relevance_score == 0.0
        assert result.airweave_system_metadata.source_name == "slack"
        assert result.airweave_system_metadata.entity_type == "SlackMessageEntity"
        assert result.airweave_system_metadata.sync_id is None
        assert result.airweave_system_metadata.sync_job_id is None
        assert result.airweave_system_metadata.chunk_index == 0
        assert result.airweave_system_metadata.original_entity_id == "msg-42"

    def test_breadcrumbs_converted(self):
        entity = _make_slack_entity()
        result = SearchPlanExecutor._entity_to_search_result(entity, "slack")

        assert len(result.breadcrumbs) == 1
        assert result.breadcrumbs[0].name == "#general"
        assert result.breadcrumbs[0].entity_type == "SlackChannel"

    def test_created_at_preserved(self):
        entity = _make_slack_entity()
        result = SearchPlanExecutor._entity_to_search_result(entity, "slack")
        assert result.created_at == datetime(2026, 3, 15, 10, 0, 0)

    def test_textual_representation_preserved(self):
        entity = _make_slack_entity(text="important info")
        result = SearchPlanExecutor._entity_to_search_result(entity, "slack")
        assert "important info" in result.textual_representation


# ═══════════════════════════════════════════════════════════════════════
# FULL EXECUTOR PIPELINE
# ═══════════════════════════════════════════════════════════════════════


class TestExecutorVectorOnly:
    """Tests for execute() when no federated sources exist."""

    @pytest.mark.asyncio
    async def test_returns_vector_results(self):
        vector_db = FakeVectorDB()
        vector_results = [_make_search_result(entity_id=f"v{i}") for i in range(3)]
        vector_db.seed_results(SearchResults(results=vector_results))

        executor = _build_executor(vector_db=vector_db)
        ctx = _make_ctx()

        results = await executor.execute(
            plan=_make_plan(),
            user_filter=[],
            collection_id="col-1",
            db=AsyncMock(),
            ctx=ctx,
            collection_readable_id="my-collection",
        )

        assert len(results.results) == 3

    @pytest.mark.asyncio
    async def test_no_source_connections_means_no_federated(self):
        """Empty sc_repo → no federated sources discovered."""
        vector_db = FakeVectorDB()
        vector_db.seed_results(SearchResults(results=[_make_search_result()]))

        executor = _build_executor(vector_db=vector_db)
        results = await executor.execute(
            plan=_make_plan(),
            user_filter=[],
            collection_id="col-1",
            db=AsyncMock(),
            ctx=_make_ctx(),
            collection_readable_id="my-collection",
        )

        assert len(results.results) == 1


class TestExecutorFederated:
    """Tests for execute() when federated sources exist."""

    @pytest.mark.asyncio
    async def test_federated_results_merged_with_vector(self):
        """Both vector and federated return results → merged via RRF."""
        # Setup vector DB
        vector_db = FakeVectorDB()
        vector_results = [_make_search_result(entity_id=f"v{i}__chunk_0") for i in range(3)]
        vector_db.seed_results(SearchResults(results=vector_results))

        # Setup federated source
        slack_entity = _make_slack_entity(entity_id="msg-1")
        fake_source = _FakeFederatedSource(entities=[slack_entity])

        sc = _make_source_connection("slack", federated=True)
        sc_repo = FakeSourceConnectionRepository()
        sc_repo.seed(sc.id, sc)
        # Seed get_by_collection_ids to return our source connection
        # FakeSourceConnectionRepository filters by sc.readable_collection_id

        source_registry = FakeSourceRegistry()
        source_registry.seed(_make_registry_entry("slack", federated=True))

        source_lifecycle = FakeSourceLifecycleService()
        source_lifecycle.seed_source(sc.id, fake_source)

        executor = _build_executor(
            vector_db=vector_db,
            sc_repo=sc_repo,
            source_registry=source_registry,
            source_lifecycle=source_lifecycle,
        )

        results = await executor.execute(
            plan=_make_plan(),
            user_filter=[],
            collection_id="col-1",
            db=AsyncMock(),
            ctx=_make_ctx(),
            collection_readable_id="my-collection",
        )

        # 3 vector + 1 federated = 4 total
        assert len(results.results) == 4
        # All should have RRF scores
        assert all(r.relevance_score > 0 for r in results.results)

    @pytest.mark.asyncio
    async def test_federated_only_collection(self):
        """Collection with only federated sources (vector returns nothing)."""
        vector_db = FakeVectorDB()
        vector_db.seed_results(SearchResults(results=[]))

        slack_entity = _make_slack_entity(entity_id="msg-1")
        fake_source = _FakeFederatedSource(entities=[slack_entity])

        sc = _make_source_connection("slack", federated=True)
        sc_repo = FakeSourceConnectionRepository()
        sc_repo.seed(sc.id, sc)
        # FakeSourceConnectionRepository filters by sc.readable_collection_id

        source_registry = FakeSourceRegistry()
        source_registry.seed(_make_registry_entry("slack", federated=True))

        source_lifecycle = FakeSourceLifecycleService()
        source_lifecycle.seed_source(sc.id, fake_source)

        executor = _build_executor(
            vector_db=vector_db,
            sc_repo=sc_repo,
            source_registry=source_registry,
            source_lifecycle=source_lifecycle,
        )

        results = await executor.execute(
            plan=_make_plan(),
            user_filter=[],
            collection_id="col-1",
            db=AsyncMock(),
            ctx=_make_ctx(),
            collection_readable_id="my-collection",
        )

        assert len(results.results) == 1
        assert results.results[0].entity_id == "msg-1__chunk_0"

    @pytest.mark.asyncio
    async def test_filter_source_name_github_excludes_slack(self):
        """User filter source_name=github → federated Slack results filtered out."""
        vector_db = FakeVectorDB()
        vector_results = [_make_search_result(entity_id="g1__chunk_0", source_name="github")]
        vector_db.seed_results(SearchResults(results=vector_results))

        slack_entity = _make_slack_entity(entity_id="msg-1")
        fake_source = _FakeFederatedSource(entities=[slack_entity])

        sc_slack = _make_source_connection("slack", federated=True)
        sc_github = _make_source_connection("github", federated=False)
        sc_repo = FakeSourceConnectionRepository()
        sc_repo.seed(sc_slack.id, sc_slack)
        sc_repo.seed(sc_github.id, sc_github)
        sc_repo._by_collection = {"my-collection": [sc_slack, sc_github]}

        source_registry = FakeSourceRegistry()
        source_registry.seed(
            _make_registry_entry("slack", federated=True),
            _make_registry_entry("github", federated=False),
        )

        source_lifecycle = FakeSourceLifecycleService()
        source_lifecycle.seed_source(sc_slack.id, fake_source)

        executor = _build_executor(
            vector_db=vector_db,
            sc_repo=sc_repo,
            source_registry=source_registry,
            source_lifecycle=source_lifecycle,
        )

        user_filter = [
            _make_filter("airweave_system_metadata.source_name", "equals", "github")
        ]

        results = await executor.execute(
            plan=_make_plan(),
            user_filter=user_filter,
            collection_id="col-1",
            db=AsyncMock(),
            ctx=_make_ctx(),
            collection_readable_id="my-collection",
        )

        # Only GitHub results should remain — Slack filtered out in-memory
        assert all(
            r.airweave_system_metadata.source_name == "github" for r in results.results
        )

    @pytest.mark.asyncio
    async def test_filter_source_name_slack_returns_federated_only(self):
        """User filter source_name=slack → vector returns nothing, federated passes."""
        vector_db = FakeVectorDB()
        vector_db.seed_results(SearchResults(results=[]))  # Vespa has no Slack data

        slack_entity = _make_slack_entity(entity_id="msg-1")
        fake_source = _FakeFederatedSource(entities=[slack_entity])

        sc = _make_source_connection("slack", federated=True)
        sc_repo = FakeSourceConnectionRepository()
        sc_repo.seed(sc.id, sc)
        # FakeSourceConnectionRepository filters by sc.readable_collection_id

        source_registry = FakeSourceRegistry()
        source_registry.seed(_make_registry_entry("slack", federated=True))

        source_lifecycle = FakeSourceLifecycleService()
        source_lifecycle.seed_source(sc.id, fake_source)

        executor = _build_executor(
            vector_db=vector_db,
            sc_repo=sc_repo,
            source_registry=source_registry,
            source_lifecycle=source_lifecycle,
        )

        user_filter = [
            _make_filter("airweave_system_metadata.source_name", "equals", "slack")
        ]

        results = await executor.execute(
            plan=_make_plan(),
            user_filter=user_filter,
            collection_id="col-1",
            db=AsyncMock(),
            ctx=_make_ctx(),
            collection_readable_id="my-collection",
        )

        assert len(results.results) == 1
        assert results.results[0].airweave_system_metadata.source_name == "slack"

    @pytest.mark.asyncio
    async def test_federated_auth_failure_returns_vector_only(self):
        """If federated source fails to instantiate, vector results still returned."""
        vector_db = FakeVectorDB()
        vector_db.seed_results(SearchResults(results=[_make_search_result()]))

        sc = _make_source_connection("slack", federated=True)
        sc_repo = FakeSourceConnectionRepository()
        sc_repo.seed(sc.id, sc)
        # FakeSourceConnectionRepository filters by sc.readable_collection_id

        source_registry = FakeSourceRegistry()
        source_registry.seed(_make_registry_entry("slack", federated=True))

        # Don't seed source_lifecycle → create() will raise
        source_lifecycle = FakeSourceLifecycleService()

        executor = _build_executor(
            vector_db=vector_db,
            sc_repo=sc_repo,
            source_registry=source_registry,
            source_lifecycle=source_lifecycle,
        )

        results = await executor.execute(
            plan=_make_plan(),
            user_filter=[],
            collection_id="col-1",
            db=AsyncMock(),
            ctx=_make_ctx(),
            collection_readable_id="my-collection",
        )

        # Should still get vector results despite federated failure
        assert len(results.results) == 1


class TestExecutorPagination:
    """Tests for offset/limit handling with federated sources."""

    def test_rrf_pagination_slice(self):
        """With offset > 0, merged results are sliced correctly."""
        vector = [_make_search_result(entity_id=f"v{i}__chunk_0") for i in range(20)]
        federated = [_make_federated_result(entity_id=f"f{i}__chunk_0") for i in range(20)]

        merged = SearchPlanExecutor._merge_with_rrf(vector, federated, k=60)

        # Simulate offset=10, limit=5
        page = merged[10:15]
        assert len(page) == 5
        # No duplicates
        assert len({r.entity_id for r in page}) == 5

    def test_rrf_first_page(self):
        """offset=0, limit=5 returns top 5 from merged."""
        vector = [_make_search_result(entity_id=f"v{i}__chunk_0") for i in range(10)]
        federated = [_make_federated_result(entity_id=f"f{i}__chunk_0") for i in range(10)]

        merged = SearchPlanExecutor._merge_with_rrf(vector, federated, k=60)
        page = merged[0:5]

        assert len(page) == 5
        # Top results should be rank-1 from each list
        assert page[0].entity_id == "v0__chunk_0"
        assert page[1].entity_id == "f0__chunk_0"
