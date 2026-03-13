"""Unit tests for AccessControlFilter operation."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from airweave.platform.access_control.schemas import AccessContext
from airweave.search.operations.access_control_filter import AccessControlFilter
from airweave.search.state import SearchState


@pytest.fixture
def organization_id():
    """Sample organization ID."""
    return uuid4()


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_access_broker():
    """Mock access broker."""
    return MagicMock()


@pytest.fixture
def mock_context():
    """Mock SearchContext."""
    context = MagicMock()
    context.readable_collection_id = "test-collection"
    context.emitter = AsyncMock()
    return context


@pytest.fixture
def mock_api_context():
    """Mock ApiContext."""
    ctx = MagicMock()
    ctx.logger = MagicMock()
    return ctx


@pytest.mark.asyncio
class TestAccessControlFilterExecution:
    """Test AccessControlFilter execute method."""

    async def test_execute_resolves_access_context_for_user(
        self,
        mock_db,
        organization_id,
        mock_access_broker,
        mock_context,
        mock_api_context,
    ):
        """Test that execute resolves access context for the user."""
        access_context = AccessContext(
            user_principal="john@acme.com",
            user_principals=["user:john@acme.com"],
            group_principals=["group:sp:engineering"],
        )
        mock_access_broker.resolve_access_context_for_collection = AsyncMock(
            return_value=access_context
        )

        operation = AccessControlFilter(
            db=mock_db,
            user_email="john@acme.com",
            organization_id=organization_id,
            access_broker=mock_access_broker,
        )

        state = SearchState()
        await operation.execute(mock_context, state, mock_api_context)

        mock_access_broker.resolve_access_context_for_collection.assert_called_once_with(
            db=mock_db,
            user_principal="john@acme.com",
            readable_collection_id="test-collection",
            organization_id=organization_id,
        )

    async def test_execute_builds_filter_with_user_principals(
        self,
        mock_db,
        organization_id,
        mock_access_broker,
        mock_context,
        mock_api_context,
    ):
        """Test that execute builds filter with resolved principals."""
        access_context = AccessContext(
            user_principal="john@acme.com",
            user_principals=["user:john@acme.com"],
            group_principals=["group:sp:engineering", "group:ad:frontend"],
        )
        mock_access_broker.resolve_access_context_for_collection = AsyncMock(
            return_value=access_context
        )

        operation = AccessControlFilter(
            db=mock_db,
            user_email="john@acme.com",
            organization_id=organization_id,
            access_broker=mock_access_broker,
        )

        state = SearchState()
        await operation.execute(mock_context, state, mock_api_context)

        assert state.filter is not None
        assert "should" in state.filter
        assert len(state.filter["should"]) == 2

    async def test_execute_writes_filter_to_state(
        self,
        mock_db,
        organization_id,
        mock_access_broker,
        mock_context,
        mock_api_context,
    ):
        """Test that execute writes filter to state.filter."""
        access_context = AccessContext(
            user_principal="john@acme.com",
            user_principals=["user:john@acme.com"],
            group_principals=["group:sp:engineering"],
        )
        mock_access_broker.resolve_access_context_for_collection = AsyncMock(
            return_value=access_context
        )

        operation = AccessControlFilter(
            db=mock_db,
            user_email="john@acme.com",
            organization_id=organization_id,
            access_broker=mock_access_broker,
        )

        state = SearchState()
        await operation.execute(mock_context, state, mock_api_context)

        assert state.filter is not None
        assert isinstance(state.filter, dict)

    async def test_execute_sets_access_principals_in_state(
        self,
        mock_db,
        organization_id,
        mock_access_broker,
        mock_context,
        mock_api_context,
    ):
        """Test that execute sets access_principals in state."""
        access_context = AccessContext(
            user_principal="john@acme.com",
            user_principals=["user:john@acme.com"],
            group_principals=["group:sp:engineering"],
        )
        mock_access_broker.resolve_access_context_for_collection = AsyncMock(
            return_value=access_context
        )

        operation = AccessControlFilter(
            db=mock_db,
            user_email="john@acme.com",
            organization_id=organization_id,
            access_broker=mock_access_broker,
        )

        state = SearchState()
        await operation.execute(mock_context, state, mock_api_context)

        assert state.access_principals is not None
        assert len(state.access_principals) == 2
        assert "user:john@acme.com" in state.access_principals
        assert "group:sp:engineering" in state.access_principals


@pytest.mark.asyncio
class TestAccessControlFilterWithoutACSources:
    """Test AccessControlFilter when collection has no AC sources."""

    async def test_execute_skips_filtering_when_no_ac_sources(
        self,
        mock_db,
        organization_id,
        mock_access_broker,
        mock_context,
        mock_api_context,
    ):
        """Test that filtering is skipped when collection has no AC sources."""
        mock_access_broker.resolve_access_context_for_collection = AsyncMock(return_value=None)

        operation = AccessControlFilter(
            db=mock_db,
            user_email="john@acme.com",
            organization_id=organization_id,
            access_broker=mock_access_broker,
        )

        state = SearchState()
        await operation.execute(mock_context, state, mock_api_context)

        assert state.filter is None
        assert state.access_principals is None

    async def test_execute_sets_access_principals_to_none_when_no_ac_sources(
        self,
        mock_db,
        organization_id,
        mock_access_broker,
        mock_context,
        mock_api_context,
    ):
        """Test access_principals is None when no AC sources."""
        mock_access_broker.resolve_access_context_for_collection = AsyncMock(return_value=None)

        operation = AccessControlFilter(
            db=mock_db,
            user_email="john@acme.com",
            organization_id=organization_id,
            access_broker=mock_access_broker,
        )

        state = SearchState()
        await operation.execute(mock_context, state, mock_api_context)

        assert state.access_principals is None

    async def test_execute_emits_skipped_event(
        self,
        mock_db,
        organization_id,
        mock_access_broker,
        mock_context,
        mock_api_context,
    ):
        """Test that skipped event is emitted when no AC sources."""
        mock_access_broker.resolve_access_context_for_collection = AsyncMock(return_value=None)

        operation = AccessControlFilter(
            db=mock_db,
            user_email="john@acme.com",
            organization_id=organization_id,
            access_broker=mock_access_broker,
        )

        state = SearchState()
        await operation.execute(mock_context, state, mock_api_context)

        mock_context.emitter.emit.assert_called_once()
        call_args = mock_context.emitter.emit.call_args
        assert call_args[0][0] == "access_control_skipped"


class TestAccessControlFilterBuildFilter:
    """Test filter building logic."""

    def test_build_filter_includes_is_public_condition(
        self, mock_db, organization_id, mock_access_broker
    ):
        """Test that filter includes is_public condition."""
        operation = AccessControlFilter(
            db=mock_db,
            user_email="john@acme.com",
            organization_id=organization_id,
            access_broker=mock_access_broker,
        )

        principals = ["user:john@acme.com", "group:sp:engineering"]
        filter_result = operation._build_access_control_filter(principals)

        assert "should" in filter_result
        conditions = filter_result["should"]

        public_condition = next(
            (c for c in conditions if c.get("key") == "access.is_public"), None
        )
        assert public_condition is not None
        assert public_condition["match"]["value"] is True

    def test_build_filter_includes_viewers_any_condition(
        self, mock_db, organization_id, mock_access_broker
    ):
        """Test that filter includes viewers any condition."""
        operation = AccessControlFilter(
            db=mock_db,
            user_email="john@acme.com",
            organization_id=organization_id,
            access_broker=mock_access_broker,
        )

        principals = ["user:john@acme.com", "group:sp:engineering"]
        filter_result = operation._build_access_control_filter(principals)

        assert "should" in filter_result
        conditions = filter_result["should"]

        viewers_condition = next(
            (c for c in conditions if c.get("key") == "access.viewers"), None
        )
        assert viewers_condition is not None
        assert "any" in viewers_condition["match"]
        assert set(viewers_condition["match"]["any"]) == set(principals)

    def test_build_filter_handles_empty_principals(
        self, mock_db, organization_id, mock_access_broker
    ):
        """Test filter building with empty principals list."""
        operation = AccessControlFilter(
            db=mock_db,
            user_email="john@acme.com",
            organization_id=organization_id,
            access_broker=mock_access_broker,
        )

        filter_result = operation._build_access_control_filter([])

        assert "should" in filter_result
        conditions = filter_result["should"]
        assert len(conditions) == 1
        assert conditions[0]["key"] == "access.is_public"


class TestAccessControlFilterMerging:
    """Test filter merging with existing filters."""

    def test_merge_combines_with_existing_filter(
        self, mock_db, organization_id, mock_access_broker
    ):
        """Test that AC filter merges with existing filter."""
        operation = AccessControlFilter(
            db=mock_db,
            user_email="john@acme.com",
            organization_id=organization_id,
            access_broker=mock_access_broker,
        )

        ac_filter = {"should": [{"key": "access.is_public", "match": {"value": True}}]}
        existing_filter = {"key": "source_name", "match": {"value": "linear"}}

        merged = operation._merge_with_existing_filter(ac_filter, existing_filter)

        assert "must" in merged
        assert len(merged["must"]) == 2

    def test_merge_creates_must_condition_when_both_exist(
        self, mock_db, organization_id, mock_access_broker
    ):
        """Test that merge creates must AND condition."""
        operation = AccessControlFilter(
            db=mock_db,
            user_email="john@acme.com",
            organization_id=organization_id,
            access_broker=mock_access_broker,
        )

        ac_filter = {"should": [{"key": "access.is_public", "match": {"value": True}}]}
        existing_filter = {"key": "entity_type", "match": {"value": "issue"}}

        merged = operation._merge_with_existing_filter(ac_filter, existing_filter)

        assert "must" in merged
        assert ac_filter in merged["must"]
        assert existing_filter in merged["must"]

    def test_merge_returns_new_filter_when_no_existing(
        self, mock_db, organization_id, mock_access_broker
    ):
        """Test that merge returns AC filter when no existing filter."""
        operation = AccessControlFilter(
            db=mock_db,
            user_email="john@acme.com",
            organization_id=organization_id,
            access_broker=mock_access_broker,
        )

        ac_filter = {"should": [{"key": "access.is_public", "match": {"value": True}}]}

        merged = operation._merge_with_existing_filter(ac_filter, None)

        assert merged == ac_filter


class TestAccessControlFilterDependencies:
    """Test operation dependencies."""

    def test_depends_on_returns_empty_list(
        self, mock_db, organization_id, mock_access_broker
    ):
        """Test that AccessControlFilter has no dependencies."""
        operation = AccessControlFilter(
            db=mock_db,
            user_email="john@acme.com",
            organization_id=organization_id,
            access_broker=mock_access_broker,
        )

        dependencies = operation.depends_on()

        assert dependencies == []
