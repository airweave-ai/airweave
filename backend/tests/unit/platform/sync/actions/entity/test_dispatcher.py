"""Tests for EntityActionDispatcher.

Tests the dispatcher's batch filtering and handler coordination,
including skip_content_handlers filtering for collection-level deduplication.
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from airweave.platform.sync.actions.entity.dispatcher import EntityActionDispatcher
from airweave.platform.sync.actions.entity.types import (
    EntityActionBatch,
    EntityDeleteAction,
    EntityInsertAction,
    EntityUpdateAction,
)
from airweave.platform.sync.handlers.entity_postgres import EntityPostgresHandler
from airweave.platform.sync.handlers.protocol import EntityActionHandler


# =============================================================================
# Test Fixtures
# =============================================================================


class MockEntity:
    """Mock entity for testing."""

    def __init__(self, entity_id: str):
        self.entity_id = entity_id


class MockLogger:
    """Mock logger for testing."""

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        pass

    def error(self, msg: str, exc_info: bool = False) -> None:
        pass


class MockSync:
    """Mock sync object."""

    def __init__(self):
        self.id = uuid4()


class MockSyncContext:
    """Mock sync context for testing."""

    def __init__(self):
        self.sync = MockSync()
        self.logger = MockLogger()


class MockDestinationHandler(EntityActionHandler):
    """Mock destination handler for testing."""

    def __init__(self, name: str = "mock_destination"):
        self._name = name
        self.handle_batch = AsyncMock()
        self.handle_orphan_cleanup = AsyncMock()

    @property
    def name(self) -> str:
        return self._name


class MockPostgresHandler(EntityPostgresHandler):
    """Mock postgres handler for testing."""

    def __init__(self):
        # Don't call super().__init__() to avoid dependency injection
        pass

    @property
    def name(self) -> str:
        return "postgres"

    async def handle_batch(self, batch, sync_context):
        pass

    async def handle_orphan_cleanup(self, orphan_entity_ids, sync_context):
        pass


def create_insert_action(entity_id: str, skip: bool = False) -> EntityInsertAction:
    """Create an insert action for testing."""
    entity = MockEntity(entity_id)
    return EntityInsertAction(
        entity=entity,
        entity_definition_id=uuid4(),
        skip_content_handlers=skip,
    )


def create_update_action(entity_id: str) -> EntityUpdateAction:
    """Create an update action for testing."""
    entity = MockEntity(entity_id)
    return EntityUpdateAction(
        entity=entity,
        entity_definition_id=uuid4(),
        db_id=uuid4(),
    )


def create_delete_action(entity_id: str) -> EntityDeleteAction:
    """Create a delete action for testing."""
    entity = MockEntity(entity_id)
    return EntityDeleteAction(
        entity=entity,
        entity_definition_id=uuid4(),
        db_id=uuid4(),
    )


# =============================================================================
# Test Classes
# =============================================================================


class TestDispatcherInit:
    """Test EntityActionDispatcher initialization."""

    def test_separates_postgres_from_destination_handlers(self):
        """Test that postgres handler is separated from destination handlers."""
        dest_handler = MockDestinationHandler("destination")
        postgres_handler = MockPostgresHandler()

        dispatcher = EntityActionDispatcher([dest_handler, postgres_handler])

        assert len(dispatcher._destination_handlers) == 1
        assert dispatcher._destination_handlers[0] == dest_handler
        assert dispatcher._postgres_handler == postgres_handler

    def test_handles_no_postgres_handler(self):
        """Test dispatcher works without postgres handler."""
        dest_handler = MockDestinationHandler("destination")

        dispatcher = EntityActionDispatcher([dest_handler])

        assert len(dispatcher._destination_handlers) == 1
        assert dispatcher._postgres_handler is None

    def test_handles_multiple_destination_handlers(self):
        """Test dispatcher with multiple destination handlers."""
        dest1 = MockDestinationHandler("dest1")
        dest2 = MockDestinationHandler("dest2")

        dispatcher = EntityActionDispatcher([dest1, dest2])

        assert len(dispatcher._destination_handlers) == 2


class TestFilterBatchForDestinations:
    """Test _filter_batch_for_destinations method."""

    def test_filters_inserts_with_skip_content_handlers(self):
        """Test filtering removes inserts with skip_content_handlers=True."""
        dispatcher = EntityActionDispatcher([])
        ctx = MockSyncContext()

        batch = EntityActionBatch(
            inserts=[
                create_insert_action("entity-1", skip=False),  # Keep
                create_insert_action("entity-2", skip=True),   # Filter out
                create_insert_action("entity-3", skip=False),  # Keep
            ],
            updates=[create_update_action("entity-4")],
            deletes=[create_delete_action("entity-5")],
            keeps=[],
        )

        filtered = dispatcher._filter_batch_for_destinations(batch, ctx)

        assert len(filtered.inserts) == 2
        assert all(not a.skip_content_handlers for a in filtered.inserts)
        # Updates and deletes are preserved
        assert len(filtered.updates) == 1
        assert len(filtered.deletes) == 1

    def test_returns_original_when_no_filtering_needed(self):
        """Test returns original batch when no skip_content_handlers flags."""
        dispatcher = EntityActionDispatcher([])
        ctx = MockSyncContext()

        batch = EntityActionBatch(
            inserts=[
                create_insert_action("entity-1", skip=False),
                create_insert_action("entity-2", skip=False),
            ],
            updates=[],
            deletes=[],
            keeps=[],
        )

        filtered = dispatcher._filter_batch_for_destinations(batch, ctx)

        # Should be the same object (no copy needed)
        assert filtered is batch

    def test_filters_all_inserts_when_all_skipped(self):
        """Test all inserts filtered when all have skip_content_handlers=True."""
        dispatcher = EntityActionDispatcher([])
        ctx = MockSyncContext()

        batch = EntityActionBatch(
            inserts=[
                create_insert_action("entity-1", skip=True),
                create_insert_action("entity-2", skip=True),
            ],
            updates=[],
            deletes=[],
            keeps=[],
        )

        filtered = dispatcher._filter_batch_for_destinations(batch, ctx)

        assert len(filtered.inserts) == 0

    def test_preserves_existing_map(self):
        """Test filtered batch preserves existing_map."""
        dispatcher = EntityActionDispatcher([])
        ctx = MockSyncContext()

        existing_map = {("entity-1", uuid4()): MagicMock()}
        batch = EntityActionBatch(
            inserts=[create_insert_action("entity-1", skip=True)],
            updates=[],
            deletes=[],
            keeps=[],
            existing_map=existing_map,
        )

        filtered = dispatcher._filter_batch_for_destinations(batch, ctx)

        assert filtered.existing_map == existing_map


class TestDispatch:
    """Test dispatch method."""

    @pytest.mark.asyncio
    async def test_dispatch_sends_filtered_batch_to_destinations(self):
        """Test destinations receive filtered batch."""
        dest_handler = MockDestinationHandler("destination")
        dispatcher = EntityActionDispatcher([dest_handler])
        ctx = MockSyncContext()

        batch = EntityActionBatch(
            inserts=[
                create_insert_action("entity-1", skip=False),  # Keep
                create_insert_action("entity-2", skip=True),   # Filter
            ],
            updates=[],
            deletes=[],
            keeps=[],
        )

        await dispatcher.dispatch(batch, ctx)

        dest_handler.handle_batch.assert_called_once()
        received_batch = dest_handler.handle_batch.call_args[0][0]
        # Destination should receive filtered batch (1 insert)
        assert len(received_batch.inserts) == 1
        assert received_batch.inserts[0].entity.entity_id == "entity-1"

    @pytest.mark.asyncio
    async def test_dispatch_sends_full_batch_to_postgres(self):
        """Test postgres receives full batch (all inserts)."""
        postgres_handler = MockPostgresHandler()
        postgres_handler.handle_batch = AsyncMock()
        dispatcher = EntityActionDispatcher([postgres_handler])
        ctx = MockSyncContext()

        batch = EntityActionBatch(
            inserts=[
                create_insert_action("entity-1", skip=False),
                create_insert_action("entity-2", skip=True),  # Still sent to postgres
            ],
            updates=[],
            deletes=[],
            keeps=[],
        )

        await dispatcher.dispatch(batch, ctx)

        postgres_handler.handle_batch.assert_called_once()
        received_batch = postgres_handler.handle_batch.call_args[0][0]
        # Postgres should receive full batch (both inserts)
        assert len(received_batch.inserts) == 2

    @pytest.mark.asyncio
    async def test_dispatch_order_destinations_then_postgres(self):
        """Test destinations are processed before postgres."""
        dest_handler = MockDestinationHandler("destination")
        postgres_handler = MockPostgresHandler()
        postgres_handler.handle_batch = AsyncMock()
        call_order = []

        async def track_dest(*args, **kwargs):
            call_order.append("destination")

        async def track_postgres(*args, **kwargs):
            call_order.append("postgres")

        dest_handler.handle_batch = AsyncMock(side_effect=track_dest)
        postgres_handler.handle_batch = AsyncMock(side_effect=track_postgres)

        dispatcher = EntityActionDispatcher([dest_handler, postgres_handler])
        ctx = MockSyncContext()

        batch = EntityActionBatch(
            inserts=[create_insert_action("entity-1")],
            updates=[],
            deletes=[],
            keeps=[],
        )

        await dispatcher.dispatch(batch, ctx)

        assert call_order == ["destination", "postgres"]

    @pytest.mark.asyncio
    async def test_dispatch_skips_when_no_mutations(self):
        """Test dispatch returns early with no mutations."""
        dest_handler = MockDestinationHandler("destination")
        dispatcher = EntityActionDispatcher([dest_handler])
        ctx = MockSyncContext()

        batch = EntityActionBatch(
            inserts=[],
            updates=[],
            deletes=[],
            keeps=[MagicMock()],  # Only keeps
        )

        await dispatcher.dispatch(batch, ctx)

        dest_handler.handle_batch.assert_not_called()


class TestDispatchWithMixedActions:
    """Test dispatch with various action combinations."""

    @pytest.mark.asyncio
    async def test_updates_not_filtered(self):
        """Test updates are never filtered (skip_content_handlers is for inserts)."""
        dest_handler = MockDestinationHandler("destination")
        dispatcher = EntityActionDispatcher([dest_handler])
        ctx = MockSyncContext()

        batch = EntityActionBatch(
            inserts=[],
            updates=[
                create_update_action("entity-1"),
                create_update_action("entity-2"),
            ],
            deletes=[],
            keeps=[],
        )

        await dispatcher.dispatch(batch, ctx)

        dest_handler.handle_batch.assert_called_once()
        received_batch = dest_handler.handle_batch.call_args[0][0]
        assert len(received_batch.updates) == 2

    @pytest.mark.asyncio
    async def test_deletes_not_filtered(self):
        """Test deletes are never filtered."""
        dest_handler = MockDestinationHandler("destination")
        dispatcher = EntityActionDispatcher([dest_handler])
        ctx = MockSyncContext()

        batch = EntityActionBatch(
            inserts=[],
            updates=[],
            deletes=[
                create_delete_action("entity-1"),
                create_delete_action("entity-2"),
            ],
            keeps=[],
        )

        await dispatcher.dispatch(batch, ctx)

        dest_handler.handle_batch.assert_called_once()
        received_batch = dest_handler.handle_batch.call_args[0][0]
        assert len(received_batch.deletes) == 2
