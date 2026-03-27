"""Tests for InstantSearchService."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from airweave.adapters.event_bus.fake import FakeEventBus
from airweave.api.context import ApiContext
from airweave.core.events.search import SearchCompletedEvent, SearchFailedEvent
from airweave.core.exceptions import CollectionNotFoundException, InvalidInputError
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod
from airweave.domains.collections.fakes.repository import FakeCollectionRepository
from airweave.domains.search.agentic.tests.conftest import make_result
from airweave.domains.search.fakes.executor import FakeSearchPlanExecutor
from airweave.domains.search.instant.service import InstantSearchService
from airweave.domains.search.types import SearchResults
from airweave.domains.search.types.filters import (
    FilterCondition,
    FilterGroup,
    FilterOperator,
    FilterableField,
)
from airweave.domains.source_connections.fakes.repository import FakeSourceConnectionRepository
from airweave.models.collection import Collection
from airweave.models.source_connection import SourceConnection
from airweave.schemas.search_v2 import InstantSearchRequest

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


def _make_request(query: str = "test query", **kwargs) -> InstantSearchRequest:
    """Build an InstantSearchRequest with defaults."""
    return InstantSearchRequest(query=query, **kwargs)


def _make_source_connection(readable_collection_id: str = DEFAULT_READABLE_ID) -> SourceConnection:
    """Build a minimal SourceConnection model."""
    sc = SourceConnection(
        id=uuid4(),
        organization_id=DEFAULT_ORG_ID,
        name="Test Source",
        short_name="stub",
        readable_collection_id=readable_collection_id,
    )
    return sc


def _make_service(
    *,
    executor: FakeSearchPlanExecutor | None = None,
    collection_repo: FakeCollectionRepository | None = None,
    sc_repo: FakeSourceConnectionRepository | None = None,
    event_bus: FakeEventBus | None = None,
) -> tuple[
    InstantSearchService,
    FakeSearchPlanExecutor,
    FakeCollectionRepository,
    FakeSourceConnectionRepository,
    FakeEventBus,
]:
    """Build an InstantSearchService with fakes, returning the service and key fakes."""
    executor = executor or FakeSearchPlanExecutor()
    collection_repo = collection_repo or FakeCollectionRepository()
    sc_repo = sc_repo or FakeSourceConnectionRepository()
    event_bus = event_bus or FakeEventBus()

    svc = InstantSearchService(
        executor=executor,
        collection_repo=collection_repo,
        sc_repo=sc_repo,
        event_bus=event_bus,
    )
    return svc, executor, collection_repo, sc_repo, event_bus


# ── Tests ────────────────────────────────────────────────────────────


class TestInstantSearchService:
    """Tests for InstantSearchService.search()."""

    @pytest.mark.asyncio
    async def test_happy_path_emits_completed_event(self) -> None:
        """Executor returns results -> SearchCompletedEvent published."""
        svc, executor, repo, sc_repo, bus = _make_service()

        # Seed collection + source connection
        col = _make_collection()
        repo.seed_readable(DEFAULT_READABLE_ID, col)
        sc = _make_source_connection()
        sc_repo.seed(sc.id, sc)

        # Seed executor with results
        result = make_result(entity_id="ent-1", name="Result 1")
        executor.seed_result(SearchResults(results=[result]))

        results = await svc.search(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        assert len(results.results) == 1
        assert results.results[0].entity_id == "ent-1"

        # Verify completed event was published
        event = bus.assert_published("search.completed")
        assert isinstance(event, SearchCompletedEvent)
        assert event.tier.value == "instant"

    @pytest.mark.asyncio
    async def test_executor_error_emits_failed_event(self) -> None:
        """Executor raises -> SearchFailedEvent published, exception raised."""
        svc, executor, repo, sc_repo, bus = _make_service()

        # Seed collection + source connection
        col = _make_collection()
        repo.seed_readable(DEFAULT_READABLE_ID, col)
        sc = _make_source_connection()
        sc_repo.seed(sc.id, sc)

        # Seed executor with error
        executor.seed_error(RuntimeError("db down"))

        with pytest.raises(RuntimeError, match="db down"):
            await svc.search(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        # Verify failed event was published
        event = bus.assert_published("search.failed")
        assert isinstance(event, SearchFailedEvent)
        assert "db down" in event.message
        assert event.tier.value == "instant"

    @pytest.mark.asyncio
    async def test_collection_not_found_raises_404(self) -> None:
        """Collection repo returns None -> CollectionNotFoundException."""
        svc, executor, repo, sc_repo, bus = _make_service()

        # Do not seed any collection — repo returns None

        with pytest.raises(CollectionNotFoundException):
            await svc.search(AsyncMock(), _make_ctx(), "nonexistent", _make_request())

        # No SearchFailedEvent should be emitted for user errors
        assert len(bus.events) == 0

    @pytest.mark.asyncio
    async def test_collection_no_sources_raises_422(self) -> None:
        """Collection exists but has no sources -> InvalidInputError."""
        svc, executor, repo, sc_repo, bus = _make_service()

        # Seed collection but NO source connections
        col = _make_collection()
        repo.seed_readable(DEFAULT_READABLE_ID, col)

        with pytest.raises(InvalidInputError, match="has no sources"):
            await svc.search(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        # No SearchFailedEvent should be emitted for user errors
        assert len(bus.events) == 0

    @pytest.mark.asyncio
    async def test_filters_passed_to_executor(self) -> None:
        """Request with filters -> executor _calls shows filters were passed."""
        svc, executor, repo, sc_repo, bus = _make_service()

        # Seed collection + source connection
        col = _make_collection()
        repo.seed_readable(DEFAULT_READABLE_ID, col)
        sc = _make_source_connection()
        sc_repo.seed(sc.id, sc)

        # Seed executor with empty results
        executor.seed_result(SearchResults(results=[]))

        # Build a request with filters
        filter_groups = [
            FilterGroup(
                conditions=[
                    FilterCondition(
                        field=FilterableField.SYSTEM_METADATA_SOURCE_NAME,
                        operator=FilterOperator.EQUALS,
                        value="notion",
                    )
                ]
            )
        ]
        request = _make_request(filter=filter_groups)

        await svc.search(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, request)

        # Verify executor was called with the filters as user_filter
        assert len(executor._calls) == 1
        _, plan, user_filter, _ = executor._calls[0]
        assert len(user_filter) == 1
        assert user_filter[0].conditions[0].field == FilterableField.SYSTEM_METADATA_SOURCE_NAME
        assert user_filter[0].conditions[0].value == "notion"
