"""Tests for EntityPipeline — DI wiring, orphan identification, and source-hash lookup."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.domains.sync_pipeline.entity.pipeline import EntityPipeline
from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import AirweaveSystemMetadata, FileEntity

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


# ---------------------------------------------------------------------------
# Helpers for source-hash tests
# ---------------------------------------------------------------------------


class _StubFileEntity(FileEntity):
    stub_id: str = AirweaveField(..., is_entity_id=True)
    stub_name: str = AirweaveField(..., is_name=True)


def _make_registry(class_map=None):
    from airweave.domains.entities.registry import EntityDefinitionRegistry

    registry = EntityDefinitionRegistry()
    if class_map:
        registry._by_class = dict(class_map)
    return registry


def _file_entity(entity_id="f-1", source_hash=None):
    e = _StubFileEntity(
        stub_id=entity_id,
        stub_name="test.txt",
        breadcrumbs=[],
        url="https://example.com/f",
        size=100,
        file_type="text",
        source_hash=source_hash,
    )
    e.entity_id = entity_id
    e.airweave_system_metadata = AirweaveSystemMetadata(
        entity_type="_StubFileEntity",
    )
    return e


def _make_pipeline(repo=None, registry=None):
    return EntityPipeline(
        entity_tracker=MagicMock(),
        event_bus=MagicMock(),
        action_resolver=MagicMock(),
        action_dispatcher=MagicMock(),
        entity_repo=repo or MagicMock(),
        entity_registry=registry,
    )


# ---------------------------------------------------------------------------
# Constructor — entity_registry
# ---------------------------------------------------------------------------


def test_constructor_stores_entity_registry():
    registry = MagicMock()
    pipeline = _make_pipeline(registry=registry)
    assert pipeline._entity_registry is registry


def test_constructor_entity_registry_defaults_to_none():
    pipeline = EntityPipeline(
        entity_tracker=MagicMock(),
        event_bus=MagicMock(),
        action_resolver=MagicMock(),
        action_dispatcher=MagicMock(),
        entity_repo=MagicMock(),
    )
    assert pipeline._entity_registry is None


# ---------------------------------------------------------------------------
# _resolve_short_name
# ---------------------------------------------------------------------------


def test_resolve_short_name_uses_registry():
    registry = _make_registry({_StubFileEntity: "stub_file_entity"})
    pipeline = _make_pipeline(registry=registry)
    e = _file_entity()
    assert pipeline._resolve_short_name(e) == "stub_file_entity"


def test_resolve_short_name_returns_none_without_registry():
    pipeline = _make_pipeline(registry=None)
    e = _file_entity()
    assert pipeline._resolve_short_name(e) is None


def test_resolve_short_name_returns_none_for_unknown_class():
    registry = _make_registry({})
    pipeline = _make_pipeline(registry=registry)
    e = _file_entity()
    assert pipeline._resolve_short_name(e) is None


# ---------------------------------------------------------------------------
# _fetch_stored_hashes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_stored_hashes_returns_none_without_source_hash():
    """Entities without source_hash produce no DB query."""
    pipeline = _make_pipeline()
    e = _file_entity(source_hash=None)

    sync_ctx = MagicMock()
    result = await pipeline._fetch_stored_hashes([e], sync_ctx)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_stored_hashes_returns_none_without_registry():
    """Without entity_registry, short_name resolution fails and entities are skipped."""
    pipeline = _make_pipeline(registry=None)
    e = _file_entity(source_hash="sha256:abc")

    sync_ctx = MagicMock()
    result = await pipeline._fetch_stored_hashes([e], sync_ctx)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_stored_hashes_returns_content_hash_on_match():
    """When source_hash matches stored value, returns the stored content_hash."""
    registry = _make_registry({_StubFileEntity: "stub_file_entity"})
    repo = MagicMock()

    db_row = SimpleNamespace(source_hash="sha256:abc", content_hash="deadbeef")
    repo.bulk_get_by_entity_sync_and_definition = AsyncMock(
        return_value={("f-1", "stub_file_entity"): db_row}
    )

    pipeline = _make_pipeline(repo=repo, registry=registry)
    e = _file_entity(entity_id="f-1", source_hash="sha256:abc")

    sync_ctx = MagicMock()
    sync_ctx.sync = MagicMock()
    sync_ctx.sync.id = uuid4()

    with patch("airweave.db.session.get_db_context") as mock_db_ctx:
        mock_db = AsyncMock()
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await pipeline._fetch_stored_hashes([e], sync_ctx)

    assert result == {"f-1": "deadbeef"}


@pytest.mark.asyncio
async def test_fetch_stored_hashes_returns_none_on_hash_mismatch():
    """When source_hash differs from stored, returns None (no reuse)."""
    registry = _make_registry({_StubFileEntity: "stub_file_entity"})
    repo = MagicMock()

    db_row = SimpleNamespace(source_hash="sha256:old", content_hash="deadbeef")
    repo.bulk_get_by_entity_sync_and_definition = AsyncMock(
        return_value={("f-1", "stub_file_entity"): db_row}
    )

    pipeline = _make_pipeline(repo=repo, registry=registry)
    e = _file_entity(entity_id="f-1", source_hash="sha256:new")

    sync_ctx = MagicMock()
    sync_ctx.sync = MagicMock()
    sync_ctx.sync.id = uuid4()

    with patch("airweave.db.session.get_db_context") as mock_db_ctx:
        mock_db = AsyncMock()
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await pipeline._fetch_stored_hashes([e], sync_ctx)

    assert result is None


@pytest.mark.asyncio
async def test_fetch_stored_hashes_skips_when_no_stored_content_hash():
    """When DB row has source_hash but no content_hash, no reuse."""
    registry = _make_registry({_StubFileEntity: "stub_file_entity"})
    repo = MagicMock()

    db_row = SimpleNamespace(source_hash="sha256:abc", content_hash=None)
    repo.bulk_get_by_entity_sync_and_definition = AsyncMock(
        return_value={("f-1", "stub_file_entity"): db_row}
    )

    pipeline = _make_pipeline(repo=repo, registry=registry)
    e = _file_entity(entity_id="f-1", source_hash="sha256:abc")

    sync_ctx = MagicMock()
    sync_ctx.sync = MagicMock()
    sync_ctx.sync.id = uuid4()

    with patch("airweave.db.session.get_db_context") as mock_db_ctx:
        mock_db = AsyncMock()
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await pipeline._fetch_stored_hashes([e], sync_ctx)

    assert result is None
