"""Tests for DestinationHandler.

Tests the destination handler's behavior for collection-level deduplication,
specifically the skip_content_handlers flag filtering.
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


class TestDestinationHandlerSkipContentHandlers:
    """Test DestinationHandler respects skip_content_handlers flag."""

    @pytest.mark.asyncio
    async def test_handle_batch_skips_inserts_with_skip_flag(self):
        """Test handle_batch filters out inserts with skip_content_handlers=True."""
        dest = MockDestination()
        handler = DestinationHandler([dest])
        ctx = MockSyncContext()

        # Create batch with mixed inserts
        batch = EntityActionBatch(
            inserts=[
                create_insert_action("entity-1", skip=False),  # Should process
                create_insert_action("entity-2", skip=True),  # Should skip
                create_insert_action("entity-3", skip=False),  # Should process
            ],
            updates=[],
            deletes=[],
            keeps=[],
        )

        # Mock the processor
        with patch.object(handler, "_do_process_and_insert", new=AsyncMock()) as mock_process:
            await handler.handle_batch(batch, ctx)

            # Should be called with only 2 entities (not the skipped one)
            mock_process.assert_called_once()
            entities = mock_process.call_args[0][0]
            assert len(entities) == 2
            assert all(e.entity_id in ["entity-1", "entity-3"] for e in entities)

    @pytest.mark.asyncio
    async def test_handle_batch_skips_all_inserts_when_all_flagged(self):
        """Test handle_batch skips processing when all inserts have skip flag."""
        dest = MockDestination()
        handler = DestinationHandler([dest])
        ctx = MockSyncContext()

        # All inserts have skip_content_handlers=True
        batch = EntityActionBatch(
            inserts=[
                create_insert_action("entity-1", skip=True),
                create_insert_action("entity-2", skip=True),
            ],
            updates=[],
            deletes=[],
            keeps=[],
        )

        with patch.object(handler, "_do_process_and_insert", new=AsyncMock()) as mock_process:
            await handler.handle_batch(batch, ctx)

            # Should not be called since no entities to process
            mock_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_batch_still_processes_updates(self):
        """Test handle_batch still processes updates even when inserts are skipped."""
        dest = MockDestination()
        handler = DestinationHandler([dest])
        ctx = MockSyncContext()

        batch = EntityActionBatch(
            inserts=[
                create_insert_action("entity-1", skip=True),  # Skipped
            ],
            updates=[
                create_update_action("entity-2"),  # Should process
            ],
            deletes=[],
            keeps=[],
        )

        with patch.object(handler, "_do_process_and_insert", new=AsyncMock()) as mock_process:
            with patch.object(handler, "_do_delete_by_ids", new=AsyncMock()):
                await handler.handle_batch(batch, ctx)

                # Should be called with 1 entity (the update)
                mock_process.assert_called_once()
                entities = mock_process.call_args[0][0]
                assert len(entities) == 1
                assert entities[0].entity_id == "entity-2"

    @pytest.mark.asyncio
    async def test_handle_inserts_skips_flagged_actions(self):
        """Test handle_inserts filters actions with skip_content_handlers=True."""
        dest = MockDestination()
        handler = DestinationHandler([dest])
        ctx = MockSyncContext()

        actions = [
            create_insert_action("entity-1", skip=False),
            create_insert_action("entity-2", skip=True),
            create_insert_action("entity-3", skip=True),
        ]

        with patch.object(handler, "_do_process_and_insert", new=AsyncMock()) as mock_process:
            await handler.handle_inserts(actions, ctx)

            # Should only process entity-1
            mock_process.assert_called_once()
            entities = mock_process.call_args[0][0]
            assert len(entities) == 1
            assert entities[0].entity_id == "entity-1"

    @pytest.mark.asyncio
    async def test_handle_inserts_returns_early_when_all_skipped(self):
        """Test handle_inserts returns early when all actions are skipped."""
        dest = MockDestination()
        handler = DestinationHandler([dest])
        ctx = MockSyncContext()

        actions = [
            create_insert_action("entity-1", skip=True),
            create_insert_action("entity-2", skip=True),
        ]

        with patch.object(handler, "_do_process_and_insert", new=AsyncMock()) as mock_process:
            await handler.handle_inserts(actions, ctx)

            # Should not be called
            mock_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_inserts_processes_all_when_none_skipped(self):
        """Test handle_inserts processes all when no skip flags."""
        dest = MockDestination()
        handler = DestinationHandler([dest])
        ctx = MockSyncContext()

        actions = [
            create_insert_action("entity-1", skip=False),
            create_insert_action("entity-2", skip=False),
        ]

        with patch.object(handler, "_do_process_and_insert", new=AsyncMock()) as mock_process:
            await handler.handle_inserts(actions, ctx)

            mock_process.assert_called_once()
            entities = mock_process.call_args[0][0]
            assert len(entities) == 2


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
