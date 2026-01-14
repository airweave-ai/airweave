"""Tests for DestinationHandler.

Tests the destination handler's behavior. Note that skip_content_handlers filtering
is done by EntityActionDispatcher, not by individual handlers.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.platform.sync.actions.entity.types import (
    EntityActionBatch,
    EntityDeleteAction,
    EntityInsertAction,
    EntityUpdateAction,
)
from airweave.platform.sync.handlers.destination import DestinationHandler


# =============================================================================
# Test Fixtures
# =============================================================================


class MockDestination:
    """Mock destination for testing."""

    processing_requirement = MagicMock()

    def __init__(self):
        self.bulk_insert = AsyncMock()
        self.bulk_delete_by_parent_ids = AsyncMock()


class MockEntity:
    """Mock entity for testing."""

    def __init__(self, entity_id: str):
        self.entity_id = entity_id

    def model_copy(self, deep: bool = False):
        """Mock model_copy for entity copying."""
        return MockEntity(self.entity_id)


class MockLogger:
    """Mock logger for testing."""

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
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


class TestDestinationHandlerBatch:
    """Test DestinationHandler batch processing."""

    @pytest.mark.asyncio
    async def test_handle_batch_processes_inserts_and_updates(self):
        """Test handle_batch processes both inserts and updates."""
        dest = MockDestination()
        handler = DestinationHandler([dest])
        ctx = MockSyncContext()

        batch = EntityActionBatch(
            inserts=[
                create_insert_action("entity-1"),
                create_insert_action("entity-2"),
            ],
            updates=[
                create_update_action("entity-3"),
            ],
            deletes=[],
            keeps=[],
        )

        with patch.object(handler, "_do_process_and_insert", new=AsyncMock()) as mock_process:
            with patch.object(handler, "_do_delete_by_ids", new=AsyncMock()):
                await handler.handle_batch(batch, ctx)

                mock_process.assert_called_once()
                entities = mock_process.call_args[0][0]
                # Should have 3 entities: 2 inserts + 1 update
                assert len(entities) == 3

    @pytest.mark.asyncio
    async def test_handle_batch_skips_when_no_mutations(self):
        """Test handle_batch returns early with no mutations."""
        dest = MockDestination()
        handler = DestinationHandler([dest])
        ctx = MockSyncContext()

        batch = EntityActionBatch(
            inserts=[],
            updates=[],
            deletes=[],
            keeps=[MagicMock()],  # Only keeps
        )

        with patch.object(handler, "_do_process_and_insert", new=AsyncMock()) as mock_process:
            await handler.handle_batch(batch, ctx)
            mock_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_batch_deletes_before_insert_for_updates(self):
        """Test handle_batch deletes old data before inserting new for updates."""
        dest = MockDestination()
        handler = DestinationHandler([dest])
        ctx = MockSyncContext()
        call_order = []

        async def track_delete(*args, **kwargs):
            call_order.append("delete")

        async def track_process(*args, **kwargs):
            call_order.append("process")

        batch = EntityActionBatch(
            inserts=[],
            updates=[create_update_action("entity-1")],
            deletes=[],
            keeps=[],
        )

        with patch.object(handler, "_do_delete_by_ids", side_effect=track_delete):
            with patch.object(handler, "_do_process_and_insert", side_effect=track_process):
                await handler.handle_batch(batch, ctx)

        assert call_order == ["delete", "process"]


class TestDestinationHandlerInserts:
    """Test DestinationHandler insert operations."""

    @pytest.mark.asyncio
    async def test_handle_inserts_processes_all(self):
        """Test handle_inserts processes all actions."""
        dest = MockDestination()
        handler = DestinationHandler([dest])
        ctx = MockSyncContext()

        actions = [
            create_insert_action("entity-1"),
            create_insert_action("entity-2"),
        ]

        with patch.object(handler, "_do_process_and_insert", new=AsyncMock()) as mock_process:
            await handler.handle_inserts(actions, ctx)

            mock_process.assert_called_once()
            entities = mock_process.call_args[0][0]
            assert len(entities) == 2

    @pytest.mark.asyncio
    async def test_handle_inserts_empty_list(self):
        """Test handle_inserts with empty list."""
        dest = MockDestination()
        handler = DestinationHandler([dest])
        ctx = MockSyncContext()

        with patch.object(handler, "_do_process_and_insert", new=AsyncMock()) as mock_process:
            await handler.handle_inserts([], ctx)
            mock_process.assert_not_called()


class TestDestinationHandlerNoDestinations:
    """Test DestinationHandler with no destinations configured."""

    @pytest.mark.asyncio
    async def test_handle_batch_with_no_destinations(self):
        """Test handle_batch returns early with no destinations."""
        handler = DestinationHandler([])
        ctx = MockSyncContext()

        batch = EntityActionBatch(
            inserts=[create_insert_action("entity-1")],
            updates=[],
            deletes=[],
            keeps=[],
        )

        # Should not raise, just return early
        await handler.handle_batch(batch, ctx)

    @pytest.mark.asyncio
    async def test_handle_inserts_with_no_destinations(self):
        """Test handle_inserts returns early with no destinations."""
        handler = DestinationHandler([])
        ctx = MockSyncContext()

        # Should not raise
        await handler.handle_inserts([create_insert_action("entity-1")], ctx)


class TestDestinationHandlerDeletes:
    """Test DestinationHandler delete operations."""

    @pytest.mark.asyncio
    async def test_handle_deletes_processes_all(self):
        """Test handle_deletes processes all delete actions."""
        dest = MockDestination()
        handler = DestinationHandler([dest])
        ctx = MockSyncContext()

        actions = [
            create_delete_action("entity-1"),
            create_delete_action("entity-2"),
        ]

        with patch.object(handler, "_do_delete_by_ids", new=AsyncMock()) as mock_delete:
            await handler.handle_deletes(actions, ctx)

            mock_delete.assert_called_once()
            entity_ids = mock_delete.call_args[0][0]
            assert len(entity_ids) == 2
