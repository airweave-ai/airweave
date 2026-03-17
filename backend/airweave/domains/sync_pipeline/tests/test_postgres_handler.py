"""Tests for EntityPostgresHandler — insert dedup, update-not-found, delete, orphan cleanup."""

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from airweave.domains.sync_pipeline.entity.actions import (
    EntityActionBatch,
    EntityDeleteAction,
    EntityInsertAction,
    EntityUpdateAction,
)
from airweave.domains.sync_pipeline.entity.handlers.postgres import EntityPostgresHandler
from airweave.domains.sync_pipeline.exceptions import SyncFailureError

_GET_DB_CTX = "airweave.domains.sync_pipeline.entity.handlers.postgres.get_db_context"


@dataclass
class FakeSyncContext:
    sync: Any = field(default_factory=lambda: SimpleNamespace(id=uuid4()))
    sync_job: Any = field(default_factory=lambda: SimpleNamespace(id=uuid4()))
    organization_id: UUID = field(default_factory=uuid4)
    source_connection_id: UUID = field(default_factory=uuid4)
    logger: Any = field(default_factory=lambda: MagicMock())


def _make_entity(entity_id: str, hash_val: str = "abc123", definition: str = "stub"):
    meta = SimpleNamespace(hash=hash_val)
    return SimpleNamespace(
        entity_id=entity_id,
        airweave_system_metadata=meta,
    )


def _make_insert(entity_id: str, hash_val: str = "abc123", definition: str = "stub"):
    return EntityInsertAction(
        entity=_make_entity(entity_id, hash_val),
        entity_definition_short_name=definition,
    )


def _make_update(entity_id: str, hash_val: str = "new_hash", definition: str = "stub"):
    return EntityUpdateAction(
        entity=_make_entity(entity_id, hash_val),
        entity_definition_short_name=definition,
        db_id=uuid4(),
    )


def _make_delete(entity_id: str, definition: str = "stub"):
    return EntityDeleteAction(
        entity=_make_entity(entity_id),
        entity_definition_short_name=definition,
    )


class FakeEntityRepo:
    """Minimal fake for EntityRepositoryProtocol."""

    def __init__(self):
        self.bulk_create = AsyncMock(return_value=[])
        self.bulk_update_hash = AsyncMock()
        self.bulk_remove = AsyncMock(return_value=[])
        self.bulk_get_by_entity_sync_and_definition = AsyncMock(return_value={})
        self.bulk_get_by_entity_and_sync = AsyncMock(return_value={})
        self.get_by_sync_id = AsyncMock(return_value=[])


def _make_handler():
    repo = FakeEntityRepo()
    return EntityPostgresHandler(entity_repo=repo), repo


# ---------------------------------------------------------------------------
# Insert dedup
# ---------------------------------------------------------------------------


class TestDeduplicate:
    def test_dedup_keeps_latest(self):
        handler, _ = _make_handler()
        ctx = FakeSyncContext()
        a1 = _make_insert("e1", hash_val="old")
        a2 = _make_insert("e1", hash_val="new")
        a3 = _make_insert("e2", hash_val="abc")

        result = handler._deduplicate_inserts([a1, a2, a3], ctx)

        assert len(result) == 2
        ids = [a.entity_id for a in result]
        assert ids == ["e1", "e2"]
        assert result[0].entity.airweave_system_metadata.hash == "new"

    def test_no_duplicates_passthrough(self):
        handler, _ = _make_handler()
        ctx = FakeSyncContext()
        actions = [_make_insert(f"e{i}") for i in range(3)]
        result = handler._deduplicate_inserts(actions, ctx)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Insert batch
# ---------------------------------------------------------------------------


class TestDoInserts:
    @pytest.mark.asyncio
    async def test_inserts_call_bulk_create(self):
        handler, repo = _make_handler()
        ctx = FakeSyncContext()
        actions = [_make_insert("e1"), _make_insert("e2")]

        with patch(_GET_DB_CTX) as mock_db_ctx:
            mock_db = MagicMock()
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            await handler._do_inserts(actions, ctx, mock_db)

        repo.bulk_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_missing_hash_raises(self):
        handler, _ = _make_handler()
        ctx = FakeSyncContext()
        action = _make_insert("e1", hash_val=None)

        with pytest.raises(SyncFailureError, match="missing hash"):
            await handler._do_inserts([action], ctx, MagicMock())


# ---------------------------------------------------------------------------
# Update — entity not in existing_map
# ---------------------------------------------------------------------------


class TestDoUpdates:
    @pytest.mark.asyncio
    async def test_update_not_in_existing_map_raises(self):
        handler, _ = _make_handler()
        ctx = FakeSyncContext()
        action = _make_update("e1")
        existing_map: Dict[Tuple[str, str], Any] = {}

        with pytest.raises(SyncFailureError, match="not in existing_map"):
            await handler._do_updates([action], existing_map, ctx, MagicMock())

    @pytest.mark.asyncio
    async def test_update_with_valid_map(self):
        handler, repo = _make_handler()
        ctx = FakeSyncContext()
        action = _make_update("e1", hash_val="new_hash")
        db_entity = SimpleNamespace(id=uuid4())
        existing_map = {("e1", "stub"): db_entity}

        await handler._do_updates([action], existing_map, ctx, MagicMock())

        repo.bulk_update_hash.assert_called_once()
        rows = repo.bulk_update_hash.call_args[1]["rows"]
        assert len(rows) == 1
        assert rows[0][0] == db_entity.id
        assert rows[0][1] == "new_hash"

    @pytest.mark.asyncio
    async def test_update_missing_hash_raises(self):
        handler, _ = _make_handler()
        ctx = FakeSyncContext()
        action = _make_update("e1", hash_val=None)
        existing_map = {("e1", "stub"): SimpleNamespace(id=uuid4())}

        with pytest.raises(SyncFailureError, match="missing hash"):
            await handler._do_updates([action], existing_map, ctx, MagicMock())


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDoDeletes:
    @pytest.mark.asyncio
    async def test_delete_entity_exists(self):
        handler, repo = _make_handler()
        ctx = FakeSyncContext()
        action = _make_delete("e1")
        db_entity = SimpleNamespace(id=uuid4())
        existing_map = {("e1", "stub"): db_entity}

        await handler._do_deletes([action], existing_map, ctx, MagicMock())

        repo.bulk_remove.assert_called_once()
        ids = repo.bulk_remove.call_args[1]["ids"]
        assert ids == [db_entity.id]

    @pytest.mark.asyncio
    async def test_delete_entity_not_in_db_logs_debug(self):
        handler, repo = _make_handler()
        ctx = FakeSyncContext()
        action = _make_delete("e1")
        existing_map: Dict[Tuple[str, str], Any] = {}

        await handler._do_deletes([action], existing_map, ctx, MagicMock())

        repo.bulk_remove.assert_not_called()
        ctx.logger.debug.assert_called()


# ---------------------------------------------------------------------------
# Orphan cleanup
# ---------------------------------------------------------------------------


class TestOrphanCleanup:
    @pytest.mark.asyncio
    async def test_empty_orphan_ids_returns_early(self):
        handler, repo = _make_handler()
        ctx = FakeSyncContext()

        await handler.handle_orphan_cleanup([], ctx)

        repo.bulk_get_by_entity_and_sync.assert_not_called()

    @pytest.mark.asyncio
    async def test_orphans_found_and_deleted(self):
        handler, repo = _make_handler()
        ctx = FakeSyncContext()

        orphan_db_id = uuid4()
        repo.bulk_get_by_entity_and_sync = AsyncMock(
            return_value={"orphan-1": SimpleNamespace(id=orphan_db_id)}
        )

        with patch(_GET_DB_CTX) as mock_db_ctx:
            mock_db = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            await handler.handle_orphan_cleanup(["orphan-1"], ctx)

        repo.bulk_remove.assert_called_once()
        ids = repo.bulk_remove.call_args[1]["ids"]
        assert ids == [orphan_db_id]

    @pytest.mark.asyncio
    async def test_orphans_not_found_in_db(self):
        handler, repo = _make_handler()
        ctx = FakeSyncContext()

        repo.bulk_get_by_entity_and_sync = AsyncMock(return_value={})

        with patch(_GET_DB_CTX) as mock_db_ctx:
            mock_db = MagicMock()
            mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            await handler.handle_orphan_cleanup(["orphan-1"], ctx)

        repo.bulk_remove.assert_not_called()


# ---------------------------------------------------------------------------
# handle_batch (integration)
# ---------------------------------------------------------------------------


class TestFetchExistingMap:
    @pytest.mark.asyncio
    async def test_delegates_to_repo(self):
        """_fetch_existing_map calls bulk_get_by_entity_sync_and_definition with correct args."""
        handler, repo = _make_handler()
        ctx = FakeSyncContext()
        db = MagicMock()
        expected = {("e1", "stub"): MagicMock()}
        repo.bulk_get_by_entity_sync_and_definition = AsyncMock(return_value=expected)

        actions = [_make_update("e1")]
        result = await handler._fetch_existing_map(actions, ctx, db)

        repo.bulk_get_by_entity_sync_and_definition.assert_awaited_once_with(
            db=db, sync_id=ctx.sync.id, entity_requests=[("e1", "stub")]
        )
        assert result is expected

    @pytest.mark.asyncio
    async def test_empty_actions_returns_empty(self):
        handler, repo = _make_handler()
        ctx = FakeSyncContext()
        repo.bulk_get_by_entity_sync_and_definition = AsyncMock(return_value={})

        result = await handler._fetch_existing_map([], ctx, MagicMock())

        assert result == {}


class TestHandleBatch:
    @pytest.mark.asyncio
    async def test_no_mutations_returns_early(self):
        handler, repo = _make_handler()
        ctx = FakeSyncContext()
        batch = EntityActionBatch()

        await handler.handle_batch(batch, ctx, MagicMock())

        repo.bulk_create.assert_not_called()
