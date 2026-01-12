"""Tests for ArfHandler.

Tests the ARF handler's behavior for collection-level deduplication,
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
from airweave.platform.sync.handlers.arf import ArfHandler


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


class TestArfHandlerSkipContentHandlers:
    """Test ArfHandler respects skip_content_handlers flag."""

    @pytest.mark.asyncio
    async def test_handle_batch_skips_inserts_with_skip_flag(self):
        """Test handle_batch filters out inserts with skip_content_handlers=True."""
        handler = ArfHandler()
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

        with patch.object(handler, "handle_inserts", new=AsyncMock()) as mock_handle:
            await handler.handle_batch(batch, ctx)

            # Should be called with filtered list (2 inserts)
            mock_handle.assert_called_once()
            actions = mock_handle.call_args[0][0]
            assert len(actions) == 2
            assert all(not a.skip_content_handlers for a in actions)

    @pytest.mark.asyncio
    async def test_handle_batch_does_not_call_handle_inserts_when_all_skipped(self):
        """Test handle_batch doesn't call handle_inserts when all inserts skipped."""
        handler = ArfHandler()
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

        with patch.object(handler, "handle_inserts", new=AsyncMock()) as mock_handle:
            await handler.handle_batch(batch, ctx)

            # Should not be called
            mock_handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_batch_still_processes_updates(self):
        """Test handle_batch still processes updates."""
        handler = ArfHandler()
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

        with patch.object(handler, "handle_updates", new=AsyncMock()) as mock_updates:
            with patch.object(handler, "handle_inserts", new=AsyncMock()) as mock_inserts:
                await handler.handle_batch(batch, ctx)

                # Updates should still be called
                mock_updates.assert_called_once()
                # Inserts should not be called (all skipped)
                mock_inserts.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_inserts_filters_skipped_actions(self):
        """Test handle_inserts filters actions with skip_content_handlers=True."""
        handler = ArfHandler()
        ctx = MockSyncContext()

        actions = [
            create_insert_action("entity-1", skip=False),  # Process
            create_insert_action("entity-2", skip=True),  # Skip
            create_insert_action("entity-3", skip=False),  # Process
        ]

        with patch.object(handler, "_ensure_manifest", new=AsyncMock()):
            with patch.object(handler, "_do_upsert", new=AsyncMock()) as mock_upsert:
                await handler.handle_inserts(actions, ctx)

                # Should only have 2 entities
                mock_upsert.assert_called_once()
                entities = mock_upsert.call_args[0][0]
                assert len(entities) == 2
                assert all(e.entity_id in ["entity-1", "entity-3"] for e in entities)

    @pytest.mark.asyncio
    async def test_handle_inserts_returns_early_when_all_skipped(self):
        """Test handle_inserts returns early when all actions skipped."""
        handler = ArfHandler()
        ctx = MockSyncContext()

        actions = [
            create_insert_action("entity-1", skip=True),
            create_insert_action("entity-2", skip=True),
        ]

        with patch.object(handler, "_ensure_manifest", new=AsyncMock()) as mock_manifest:
            with patch.object(handler, "_do_upsert", new=AsyncMock()) as mock_upsert:
                await handler.handle_inserts(actions, ctx)

                # Should not call manifest or upsert
                mock_manifest.assert_not_called()
                mock_upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_inserts_processes_all_when_none_skipped(self):
        """Test handle_inserts processes all when no skip flags."""
        handler = ArfHandler()
        ctx = MockSyncContext()

        actions = [
            create_insert_action("entity-1", skip=False),
            create_insert_action("entity-2", skip=False),
            create_insert_action("entity-3", skip=False),
        ]

        with patch.object(handler, "_ensure_manifest", new=AsyncMock()):
            with patch.object(handler, "_do_upsert", new=AsyncMock()) as mock_upsert:
                await handler.handle_inserts(actions, ctx)

                mock_upsert.assert_called_once()
                entities = mock_upsert.call_args[0][0]
                assert len(entities) == 3

    @pytest.mark.asyncio
    async def test_handle_inserts_empty_list(self):
        """Test handle_inserts with empty list."""
        handler = ArfHandler()
        ctx = MockSyncContext()

        with patch.object(handler, "_ensure_manifest", new=AsyncMock()) as mock_manifest:
            with patch.object(handler, "_do_upsert", new=AsyncMock()) as mock_upsert:
                await handler.handle_inserts([], ctx)

                # Should not call anything
                mock_manifest.assert_not_called()
                mock_upsert.assert_not_called()


class TestArfHandlerDeletes:
    """Test ArfHandler delete operations (not affected by skip flag)."""

    @pytest.mark.asyncio
    async def test_handle_deletes_processes_all(self):
        """Test handle_deletes processes all delete actions."""
        handler = ArfHandler()
        ctx = MockSyncContext()

        actions = [
            create_delete_action("entity-1"),
            create_delete_action("entity-2"),
        ]

        with patch.object(handler, "_do_delete", new=AsyncMock()) as mock_delete:
            await handler.handle_deletes(actions, ctx)

            mock_delete.assert_called_once()
            entity_ids = mock_delete.call_args[0][0]
            assert len(entity_ids) == 2
