"""Tests for EntityPipeline — DI wiring, orphan identification, and source-hash lookup."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.domains.sync_pipeline.entity.pipeline import EntityPipeline
from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup
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

    with patch("airweave.domains.sync_pipeline.entity.pipeline.get_db_context") as mock_db_ctx:
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

    with patch("airweave.domains.sync_pipeline.entity.pipeline.get_db_context") as mock_db_ctx:
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


def _make_lookup(cache=None):
    """Build a SourceHashLookup with a prepopulated cache."""
    from airweave.domains.sync_pipeline.source_hash_lookup import StoredEntityHashes

    lookup = SourceHashLookup(sync_id=uuid4(), logger=MagicMock())
    lookup._prefetched = True
    if cache:
        for eid, (sh, ch, comp) in cache.items():
            lookup._cache[eid] = StoredEntityHashes(
                source_hash=sh, content_hash=ch, composite_hash=comp,
            )
    return lookup


def _make_pipeline(repo=None, lookup=None):
    return EntityPipeline(
        entity_tracker=MagicMock(),
        event_bus=MagicMock(),
        action_resolver=MagicMock(),
        action_dispatcher=MagicMock(),
        entity_repo=repo or MagicMock(),
        source_hash_lookup=lookup,
    )


# ---------------------------------------------------------------------------
# Constructor — source_hash_lookup
# ---------------------------------------------------------------------------


def test_constructor_stores_source_hash_lookup():
    lookup = MagicMock()
    pipeline = _make_pipeline(lookup=lookup)
    assert pipeline._source_hash_lookup is lookup


def test_constructor_source_hash_lookup_defaults_to_none():
    pipeline = EntityPipeline(
        entity_tracker=MagicMock(),
        event_bus=MagicMock(),
        action_resolver=MagicMock(),
        action_dispatcher=MagicMock(),
        entity_repo=MagicMock(),
    )
    assert pipeline._source_hash_lookup is None


# ---------------------------------------------------------------------------
# _collect_reusable_content_hashes
# ---------------------------------------------------------------------------


def test_collect_returns_none_without_lookup():
    """Without a SourceHashLookup, returns None."""
    pipeline = _make_pipeline(lookup=None)
    e = _file_entity(source_hash="sha256:abc")

    sync_ctx = MagicMock()
    result = pipeline._collect_reusable_content_hashes([e], sync_ctx)

    assert result is None


def test_collect_returns_none_without_source_hash():
    """Entities without source_hash are skipped."""
    lookup = _make_lookup()
    pipeline = _make_pipeline(lookup=lookup)
    e = _file_entity(source_hash=None)

    sync_ctx = MagicMock()
    result = pipeline._collect_reusable_content_hashes([e], sync_ctx)

    assert result is None


def test_collect_returns_content_hash_on_match():
    """When source_hash matches stored value, returns content_hash."""
    lookup = _make_lookup(cache={
        "f-1": ("sha256:abc", "deadbeef", "composite123"),
    })
    pipeline = _make_pipeline(lookup=lookup)
    e = _file_entity(entity_id="f-1", source_hash="sha256:abc")

    sync_ctx = MagicMock()
    result = pipeline._collect_reusable_content_hashes([e], sync_ctx)

    assert result == {"f-1": "deadbeef"}


def test_collect_returns_none_on_hash_mismatch():
    """When source_hash differs from stored, no content_hash returned."""
    lookup = _make_lookup(cache={
        "f-1": ("sha256:old", "deadbeef", "composite123"),
    })
    pipeline = _make_pipeline(lookup=lookup)
    e = _file_entity(entity_id="f-1", source_hash="sha256:new")

    sync_ctx = MagicMock()
    result = pipeline._collect_reusable_content_hashes([e], sync_ctx)

    assert result is None


def test_collect_returns_none_when_no_stored_content_hash():
    """When stored entry has no content_hash, no reuse."""
    lookup = _make_lookup(cache={
        "f-1": ("sha256:abc", None, "composite123"),
    })
    pipeline = _make_pipeline(lookup=lookup)
    e = _file_entity(entity_id="f-1", source_hash="sha256:abc")

    sync_ctx = MagicMock()
    result = pipeline._collect_reusable_content_hashes([e], sync_ctx)

    assert result is None


def test_collect_returns_none_for_entity_not_in_cache():
    """Entity not in cache returns None."""
    lookup = _make_lookup(cache={})
    pipeline = _make_pipeline(lookup=lookup)
    e = _file_entity(entity_id="f-1", source_hash="sha256:abc")

    sync_ctx = MagicMock()
    result = pipeline._collect_reusable_content_hashes([e], sync_ctx)

    assert result is None
