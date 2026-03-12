"""Tests for EntityActionResolver — DI wiring and action resolution."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.domains.sync_pipeline.entity_action_resolver import EntityActionResolver
from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import (
    AirweaveSystemMetadata,
    BaseEntity,
    DeletionEntity,
)
from airweave.platform.sync.actions.entity.types import (
    EntityInsertAction,
    EntityKeepAction,
    EntityUpdateAction,
)
from airweave.platform.sync.exceptions import SyncFailureError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubEntity(BaseEntity):
    """Minimal concrete entity for testing."""

    stub_id: str = AirweaveField(..., is_entity_id=True)
    stub_name: str = AirweaveField(..., is_name=True)


class _StubDeletion(DeletionEntity):
    """Minimal deletion entity for testing."""

    deletes_entity_class = _StubEntity
    stub_id: str = AirweaveField(..., is_entity_id=True)
    stub_name: str = AirweaveField(..., is_name=True)


def _entity(entity_id="e-1", hash_val="abc123"):
    """Create a _StubEntity with entity_id set (normally done by pipeline enrichment)."""
    e = _StubEntity(stub_id=entity_id, stub_name="test", breadcrumbs=[])
    e.entity_id = entity_id
    e.airweave_system_metadata = AirweaveSystemMetadata(hash=hash_val)
    return e


def _sync_context():
    ctx = MagicMock()
    ctx.sync = MagicMock()
    ctx.sync.id = uuid4()
    ctx.logger = MagicMock()
    ctx.execution_config = None
    return ctx


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def test_constructor_stores_entity_repo():
    """entity_repo is stored on the instance."""
    repo = MagicMock()
    entity_map = {_StubEntity: "stub"}
    resolver = EntityActionResolver(entity_map=entity_map, entity_repo=repo)
    assert resolver._entity_repo is repo


# ---------------------------------------------------------------------------
# resolve_entity_definition_short_name
# ---------------------------------------------------------------------------


def test_resolve_short_name_direct():
    """Direct class lookup returns short_name."""
    repo = MagicMock()
    resolver = EntityActionResolver(entity_map={_StubEntity: "stub"}, entity_repo=repo)
    e = _entity()
    assert resolver.resolve_entity_definition_short_name(e) == "stub"


def test_resolve_short_name_deletion_entity():
    """DeletionEntity falls back to deletes_entity_class."""
    repo = MagicMock()
    resolver = EntityActionResolver(entity_map={_StubEntity: "stub"}, entity_repo=repo)
    d = _StubDeletion(stub_id="del-1", stub_name="del", deletion_status="removed", breadcrumbs=[])
    assert resolver.resolve_entity_definition_short_name(d) == "stub"


def test_resolve_short_name_unmapped():
    """Unknown entity type returns None."""
    repo = MagicMock()
    resolver = EntityActionResolver(entity_map={}, entity_repo=repo)
    e = _entity()
    assert resolver.resolve_entity_definition_short_name(e) is None


# ---------------------------------------------------------------------------
# resolve — delegates to entity_repo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_insert_when_no_existing():
    """New entity (not in DB) → INSERT action."""
    repo = MagicMock()
    repo.bulk_get_by_entity_sync_and_definition = AsyncMock(return_value={})

    resolver = EntityActionResolver(entity_map={_StubEntity: "stub"}, entity_repo=repo)
    ctx = _sync_context()
    e = _entity(entity_id="new-1", hash_val="h1")

    with patch("airweave.db.session.get_db_context") as mock_db_ctx:
        mock_db = AsyncMock()
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        batch = await resolver.resolve([e], ctx)

    assert len(batch.inserts) == 1
    assert isinstance(batch.inserts[0], EntityInsertAction)
    assert batch.inserts[0].entity is e
    repo.bulk_get_by_entity_sync_and_definition.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_update_when_hash_changed():
    """Existing entity with changed hash → UPDATE action."""
    db_entity = MagicMock()
    db_entity.id = uuid4()
    db_entity.hash = "old-hash"

    repo = MagicMock()
    repo.bulk_get_by_entity_sync_and_definition = AsyncMock(
        return_value={("e-1", "stub"): db_entity}
    )

    resolver = EntityActionResolver(entity_map={_StubEntity: "stub"}, entity_repo=repo)
    ctx = _sync_context()
    e = _entity(entity_id="e-1", hash_val="new-hash")

    with patch("airweave.db.session.get_db_context") as mock_db_ctx:
        mock_db = AsyncMock()
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        batch = await resolver.resolve([e], ctx)

    assert len(batch.updates) == 1
    assert isinstance(batch.updates[0], EntityUpdateAction)
    assert batch.updates[0].db_id == db_entity.id


@pytest.mark.asyncio
async def test_resolve_keep_when_hash_matches():
    """Existing entity with same hash → KEEP action."""
    db_entity = MagicMock()
    db_entity.id = uuid4()
    db_entity.hash = "same-hash"

    repo = MagicMock()
    repo.bulk_get_by_entity_sync_and_definition = AsyncMock(
        return_value={("e-1", "stub"): db_entity}
    )

    resolver = EntityActionResolver(entity_map={_StubEntity: "stub"}, entity_repo=repo)
    ctx = _sync_context()
    e = _entity(entity_id="e-1", hash_val="same-hash")

    with patch("airweave.db.session.get_db_context") as mock_db_ctx:
        mock_db = AsyncMock()
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        batch = await resolver.resolve([e], ctx)

    assert len(batch.keeps) == 1
    assert isinstance(batch.keeps[0], EntityKeepAction)


@pytest.mark.asyncio
async def test_resolve_raises_on_unmapped_entity():
    """Entity type not in entity_map → SyncFailureError."""
    repo = MagicMock()
    resolver = EntityActionResolver(entity_map={}, entity_repo=repo)
    ctx = _sync_context()
    e = _entity()

    with pytest.raises(SyncFailureError, match="not in entity_map"):
        await resolver.resolve([e], ctx)
