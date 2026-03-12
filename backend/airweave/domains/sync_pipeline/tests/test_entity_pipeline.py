"""Tests for EntityPipeline — DI wiring and orphan identification."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.domains.sync_pipeline.entity_pipeline import EntityPipeline


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def test_constructor_stores_entity_repo():
    """entity_repo is stored on the instance."""
    repo = MagicMock()
    pipeline = EntityPipeline(
        entity_tracker=MagicMock(),
        event_bus=MagicMock(),
        action_resolver=MagicMock(),
        action_dispatcher=MagicMock(),
        entity_repo=repo,
    )
    assert pipeline._entity_repo is repo


def test_constructor_initializes_batch_seq():
    """_batch_seq starts at 0."""
    pipeline = EntityPipeline(
        entity_tracker=MagicMock(),
        event_bus=MagicMock(),
        action_resolver=MagicMock(),
        action_dispatcher=MagicMock(),
        entity_repo=MagicMock(),
    )
    assert pipeline._batch_seq == 0


# ---------------------------------------------------------------------------
# _identify_orphans — uses entity_repo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_identify_orphans_uses_entity_repo():
    """_identify_orphans calls entity_repo.get_by_sync_id, not crud."""
    sync_id = uuid4()
    repo = MagicMock()

    stored_entity_1 = MagicMock()
    stored_entity_1.entity_id = "kept-1"
    stored_entity_1.entity_definition_short_name = "stub"

    stored_entity_2 = MagicMock()
    stored_entity_2.entity_id = "orphan-1"
    stored_entity_2.entity_definition_short_name = "stub"

    repo.get_by_sync_id = AsyncMock(return_value=[stored_entity_1, stored_entity_2])

    tracker = MagicMock()
    tracker.get_all_encountered_ids_flat.return_value = {"kept-1"}

    pipeline = EntityPipeline(
        entity_tracker=tracker,
        event_bus=MagicMock(),
        action_resolver=MagicMock(),
        action_dispatcher=MagicMock(),
        entity_repo=repo,
    )

    sync_context = MagicMock()
    sync_context.sync = MagicMock()
    sync_context.sync.id = sync_id

    with patch("airweave.db.session.get_db_context") as mock_db_ctx:
        mock_db = AsyncMock()
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        orphans = await pipeline._identify_orphans(sync_context)

    repo.get_by_sync_id.assert_awaited_once_with(db=mock_db, sync_id=sync_id)
    assert orphans == {"stub": ["orphan-1"]}


@pytest.mark.asyncio
async def test_identify_orphans_empty_when_all_encountered():
    """No orphans when all stored entities were encountered."""
    repo = MagicMock()

    stored = MagicMock()
    stored.entity_id = "e-1"
    stored.entity_definition_short_name = "stub"
    repo.get_by_sync_id = AsyncMock(return_value=[stored])

    tracker = MagicMock()
    tracker.get_all_encountered_ids_flat.return_value = {"e-1"}

    pipeline = EntityPipeline(
        entity_tracker=tracker,
        event_bus=MagicMock(),
        action_resolver=MagicMock(),
        action_dispatcher=MagicMock(),
        entity_repo=repo,
    )

    sync_context = MagicMock()
    sync_context.sync = MagicMock()
    sync_context.sync.id = uuid4()

    with patch("airweave.db.session.get_db_context") as mock_db_ctx:
        mock_db = AsyncMock()
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        orphans = await pipeline._identify_orphans(sync_context)

    assert orphans == {}
