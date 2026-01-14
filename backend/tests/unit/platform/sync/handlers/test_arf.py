"""Tests for ArfHandler.

Tests the ARF handler's behavior. Note that skip_content_handlers filtering
is done by EntityActionDispatcher, not by individual handlers.
"""

from unittest.mock import AsyncMock, patch
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


class TestArfHandlerBatch:
    """Test ArfHandler batch processing."""

    @pytest.mark.asyncio
    async def test_handle_batch_processes_all_inserts(self):
        """Test handle_batch processes all inserts (no filtering at handler level)."""
        handler = ArfHandler()
        ctx = MockSyncContext()

        # Create batch with inserts
        batch = EntityActionBatch(
            inserts=[
                create_insert_action("entity-1"),
                create_insert_action("entity-2"),
                create_insert_action("entity-3"),
            ],
            updates=[],
            deletes=[],
            keeps=[],
        )

        with patch.object(handler, "handle_inserts", new=AsyncMock()) as mock_handle:
            await handler.handle_batch(batch, ctx)

            mock_handle.assert_called_once()
            actions = mock_handle.call_args[0][0]
            assert len(actions) == 3

    @pytest.mark.asyncio
    async def test_handle_batch_does_not_call_handle_inserts_when_empty(self):
        """Test handle_batch doesn't call handle_inserts when no inserts."""
        handler = ArfHandler()
        ctx = MockSyncContext()

        batch = EntityActionBatch(
            inserts=[],
            updates=[create_update_action("entity-1")],
            deletes=[],
            keeps=[],
        )

        with patch.object(handler, "handle_inserts", new=AsyncMock()) as mock_inserts:
            with patch.object(handler, "handle_updates", new=AsyncMock()):
                await handler.handle_batch(batch, ctx)
                mock_inserts.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_batch_processes_updates(self):
        """Test handle_batch processes updates."""
        handler = ArfHandler()
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

        with patch.object(handler, "handle_updates", new=AsyncMock()) as mock_updates:
            await handler.handle_batch(batch, ctx)

            mock_updates.assert_called_once()
            actions = mock_updates.call_args[0][0]
            assert len(actions) == 2

    @pytest.mark.asyncio
    async def test_handle_batch_processes_deletes_first(self):
        """Test handle_batch processes deletes before updates and inserts."""
        handler = ArfHandler()
        ctx = MockSyncContext()
        call_order = []

        async def track_deletes(*args, **kwargs):
            call_order.append("deletes")

        async def track_updates(*args, **kwargs):
            call_order.append("updates")

        async def track_inserts(*args, **kwargs):
            call_order.append("inserts")

        batch = EntityActionBatch(
            inserts=[create_insert_action("entity-3")],
            updates=[create_update_action("entity-2")],
            deletes=[create_delete_action("entity-1")],
            keeps=[],
        )

        with patch.object(handler, "handle_deletes", side_effect=track_deletes):
            with patch.object(handler, "handle_updates", side_effect=track_updates):
                with patch.object(handler, "handle_inserts", side_effect=track_inserts):
                    await handler.handle_batch(batch, ctx)

        assert call_order == ["deletes", "updates", "inserts"]


class TestArfHandlerInserts:
    """Test ArfHandler insert operations."""

    @pytest.mark.asyncio
    async def test_handle_inserts_processes_all(self):
        """Test handle_inserts processes all actions."""
        handler = ArfHandler()
        ctx = MockSyncContext()

        actions = [
            create_insert_action("entity-1"),
            create_insert_action("entity-2"),
            create_insert_action("entity-3"),
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

    @pytest.mark.asyncio
    async def test_handle_inserts_ensures_manifest(self):
        """Test handle_inserts ensures manifest exists before upsert."""
        handler = ArfHandler()
        ctx = MockSyncContext()
        call_order = []

        async def track_manifest(*args, **kwargs):
            call_order.append("manifest")

        async def track_upsert(*args, **kwargs):
            call_order.append("upsert")

        actions = [create_insert_action("entity-1")]

        with patch.object(handler, "_ensure_manifest", side_effect=track_manifest):
            with patch.object(handler, "_do_upsert", side_effect=track_upsert):
                await handler.handle_inserts(actions, ctx)

        assert call_order == ["manifest", "upsert"]


class TestArfHandlerDeletes:
    """Test ArfHandler delete operations."""

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

    @pytest.mark.asyncio
    async def test_handle_deletes_empty_list(self):
        """Test handle_deletes with empty list."""
        handler = ArfHandler()
        ctx = MockSyncContext()

        with patch.object(handler, "_do_delete", new=AsyncMock()) as mock_delete:
            await handler.handle_deletes([], ctx)
            mock_delete.assert_not_called()
