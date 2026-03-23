"""Tests for ClassicSearchService."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from airweave.adapters.event_bus.fake import FakeEventBus
from airweave.adapters.llm.fakes import FakeLLM
from airweave.adapters.reranker.fakes.reranker import FakeReranker
from airweave.api.context import ApiContext
from airweave.core.events.search import SearchCompletedEvent, SearchFailedEvent
from airweave.core.exceptions import CollectionNotFoundException
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod
from airweave.domains.collections.fakes.repository import FakeCollectionRepository
from airweave.domains.search.agentic.tests.conftest import make_model_spec, make_result
from airweave.domains.search.classic.service import ClassicSearchService
from airweave.domains.search.classic.types import ClassicSearchStrategy
from airweave.domains.search.fakes.executor import FakeSearchPlanExecutor
from airweave.domains.search.fakes.metadata_builder import FakeCollectionMetadataBuilder
from airweave.domains.search.types import SearchResults
from airweave.domains.search.types.plan import RetrievalStrategy, SearchQuery
from airweave.models.collection import Collection
from airweave.schemas.search_v2 import ClassicSearchRequest

# ── Constants ────────────────────────────────────────────────────────

DEFAULT_ORG_ID = uuid4()
DEFAULT_COLLECTION_ID = uuid4()
DEFAULT_READABLE_ID = "test-col"


# ── Helpers ──────────────────────────────────────────────────────────


def _make_ctx() -> ApiContext:
    """Build a minimal ApiContext for tests."""
    from airweave.schemas.organization import Organization

    now = datetime.now(timezone.utc)
    org = Organization(
        id=str(DEFAULT_ORG_ID),
        name="Test Org",
        created_at=now,
        modified_at=now,
        enabled_features=[],
    )
    return ApiContext(
        request_id="test-req-001",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        auth_metadata={},
        logger=logger.with_context(request_id="test-req-001"),
    )


def _make_collection() -> Collection:
    """Build a minimal Collection model."""
    now = datetime.now(timezone.utc)
    col = Collection(
        id=DEFAULT_COLLECTION_ID,
        name="Test Collection",
        readable_id=DEFAULT_READABLE_ID,
        organization_id=DEFAULT_ORG_ID,
        vector_db_deployment_metadata_id=uuid4(),
    )
    col.created_at = now
    col.modified_at = now
    return col


def _make_strategy(primary: str = "test query", variations: list[str] | None = None) -> ClassicSearchStrategy:
    """Build a ClassicSearchStrategy with sensible defaults."""
    return ClassicSearchStrategy(
        query=SearchQuery(primary=primary, variations=variations or ["test variation"]),
        retrieval_strategy=RetrievalStrategy.HYBRID,
        filter_groups=[],
    )


def _make_request(query: str = "test query") -> ClassicSearchRequest:
    """Build a ClassicSearchRequest with defaults."""
    return ClassicSearchRequest(query=query)


def _make_service(
    *,
    llm: FakeLLM | None = None,
    reranker: FakeReranker | None = None,
    executor: FakeSearchPlanExecutor | None = None,
    collection_repo: FakeCollectionRepository | None = None,
    metadata_builder: FakeCollectionMetadataBuilder | None = None,
    event_bus: FakeEventBus | None = None,
) -> tuple[ClassicSearchService, FakeLLM, FakeSearchPlanExecutor, FakeCollectionRepository, FakeEventBus]:
    """Build a ClassicSearchService with fakes, returning the service and key fakes."""
    llm = llm or FakeLLM(model_spec=make_model_spec())
    executor = executor or FakeSearchPlanExecutor()
    collection_repo = collection_repo or FakeCollectionRepository()
    metadata_builder = metadata_builder or FakeCollectionMetadataBuilder()
    event_bus = event_bus or FakeEventBus()

    svc = ClassicSearchService(
        llm=llm,
        reranker=reranker,
        executor=executor,
        collection_repo=collection_repo,
        metadata_builder=metadata_builder,
        event_bus=event_bus,
    )
    return svc, llm, executor, collection_repo, event_bus


# ── Tests ────────────────────────────────────────────────────────────


class TestClassicSearchService:
    """Tests for ClassicSearchService.search()."""

    @pytest.mark.asyncio
    async def test_happy_path_emits_completed_event(self) -> None:
        """Seed LLM with valid strategy, executor with results -> SearchCompletedEvent."""
        svc, llm, executor, repo, bus = _make_service()

        # Seed collection
        col = _make_collection()
        repo.seed_readable(DEFAULT_READABLE_ID, col)

        # Seed LLM with a valid strategy
        llm.seed_structured_output(_make_strategy())

        # Seed executor with results
        result = make_result(entity_id="ent-1", name="Result 1")
        executor.seed_result(SearchResults(results=[result]))

        results = await svc.search(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        assert len(results.results) == 1
        assert results.results[0].entity_id == "ent-1"

        # Verify completed event was published
        event = bus.assert_published("search.completed")
        assert isinstance(event, SearchCompletedEvent)
        assert event.tier.value == "classic"

    @pytest.mark.asyncio
    async def test_llm_error_emits_failed_event(self) -> None:
        """Seed LLM with error -> SearchFailedEvent published, exception raised."""
        svc, llm, executor, repo, bus = _make_service()

        # Seed collection
        col = _make_collection()
        repo.seed_readable(DEFAULT_READABLE_ID, col)

        # Seed LLM with an error
        llm.seed_error(RuntimeError("LLM down"), target="structured_output")

        with pytest.raises(RuntimeError, match="LLM down"):
            await svc.search(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        # Verify failed event was published
        event = bus.assert_published("search.failed")
        assert isinstance(event, SearchFailedEvent)
        assert "LLM down" in event.message
        assert event.tier.value == "classic"

    @pytest.mark.asyncio
    async def test_executor_error_emits_failed_event(self) -> None:
        """Seed executor with error -> SearchFailedEvent published, exception raised."""
        svc, llm, executor, repo, bus = _make_service()

        # Seed collection
        col = _make_collection()
        repo.seed_readable(DEFAULT_READABLE_ID, col)

        # Seed LLM with valid strategy
        llm.seed_structured_output(_make_strategy())

        # Seed executor with error
        executor.seed_error(RuntimeError("db down"))

        with pytest.raises(RuntimeError, match="db down"):
            await svc.search(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        # Verify failed event was published
        event = bus.assert_published("search.failed")
        assert isinstance(event, SearchFailedEvent)
        assert "db down" in event.message
        assert event.tier.value == "classic"

    @pytest.mark.asyncio
    async def test_collection_not_found_raises_404(self) -> None:
        """Collection repo returns None -> CollectionNotFoundException."""
        svc, llm, executor, repo, bus = _make_service()

        # Do not seed any collection — repo returns None

        with pytest.raises(CollectionNotFoundException):
            await svc.search(AsyncMock(), _make_ctx(), "nonexistent", _make_request())

        # No SearchFailedEvent should be emitted for user errors
        assert len(bus.events) == 0

    @pytest.mark.asyncio
    async def test_empty_primary_falls_back_to_user_query(self) -> None:
        """Seed LLM with strategy where query.primary='' -> executor receives the original user query."""
        svc, llm, executor, repo, bus = _make_service()

        # Seed collection
        col = _make_collection()
        repo.seed_readable(DEFAULT_READABLE_ID, col)

        # Seed LLM with empty primary query
        llm.seed_structured_output(_make_strategy(primary=""))

        # Seed executor with results
        executor.seed_result(SearchResults(results=[]))

        user_query = "my actual query"
        await svc.search(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request(query=user_query))

        # Verify executor was called and the plan has the user's original query
        assert len(executor._calls) == 1
        _, plan, _, _ = executor._calls[0]
        assert plan.query.primary == user_query
