"""Unit tests for CollectionService.

Uses fakes for all dependencies — no DB, no Temporal, no external services.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.config import Settings
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod
from airweave.domains.collections.exceptions import (
    CollectionAlreadyExistsError,
    CollectionNotFoundError,
)
from airweave.domains.collections.fakes.repository import FakeCollectionRepository
from airweave.domains.collections.service import CollectionService
from airweave.domains.source_connections.fakes.repository import (
    FakeSourceConnectionRepository,
)
from airweave.domains.syncs.fakes.sync_lifecycle_service import FakeSyncLifecycleService
from airweave.models.collection import Collection
from airweave.schemas.organization import Organization

NOW = datetime.now(timezone.utc)
ORG_ID = uuid4()
COLLECTION_ID = uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ctx() -> ApiContext:
    org = Organization(id=str(ORG_ID), name="Test Org", created_at=NOW, modified_at=NOW)
    return ApiContext(
        request_id="test-req",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        logger=logger.with_context(request_id="test-req"),
    )


def _collection(
    id: UUID = COLLECTION_ID,
    name: str = "Test Collection",
    readable_id: str = "test-collection",
) -> MagicMock:
    col = MagicMock(spec=Collection)
    col.id = id
    col.name = name
    col.readable_id = readable_id
    col.organization_id = ORG_ID
    # Fields required by schemas.Collection.model_validate (used in delete snapshot)
    col.vector_size = 1536
    col.embedding_model_name = "text-embedding-3-small"
    col.sync_config = None
    col.created_at = NOW
    col.modified_at = NOW
    col.created_by_email = None
    col.modified_by_email = None
    col.status = "NEEDS SOURCE"
    return col


class _FakeEventBus:
    """Minimal fake for EventBus.publish."""

    def __init__(self) -> None:
        self.events: list = []

    async def publish(self, event) -> None:
        self.events.append(event)


def _fake_settings(**overrides) -> MagicMock:
    """Build a fake Settings with sensible defaults."""
    s = MagicMock(spec=Settings)
    s.EMBEDDING_DIMENSIONS = overrides.get("EMBEDDING_DIMENSIONS", 1536)
    return s


def _build_service(
    collection_repo=None,
    sc_repo=None,
    sync_lifecycle=None,
    event_bus=None,
    settings=None,
) -> CollectionService:
    return CollectionService(
        collection_repo=collection_repo or FakeCollectionRepository(),
        sc_repo=sc_repo or FakeSourceConnectionRepository(),
        sync_lifecycle=sync_lifecycle or FakeSyncLifecycleService(),
        event_bus=event_bus or _FakeEventBus(),
        settings=settings or _fake_settings(),
    )


# ---------------------------------------------------------------------------
# list() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_empty():
    """list() returns empty list when no collections exist."""
    svc = _build_service()
    result = await svc.list(MagicMock(), ctx=_ctx())
    assert result == []


@pytest.mark.asyncio
async def test_list_returns_seeded_items():
    """list() returns all seeded collections."""
    repo = FakeCollectionRepository()
    c1 = _collection(id=uuid4(), readable_id="alpha")
    c2 = _collection(id=uuid4(), readable_id="beta")
    repo.seed_readable("alpha", c1)
    repo.seed_readable("beta", c2)

    svc = _build_service(collection_repo=repo)
    result = await svc.list(MagicMock(), ctx=_ctx())
    assert len(result) == 2


@pytest.mark.asyncio
async def test_list_skip_limit():
    """list() respects skip and limit."""
    repo = FakeCollectionRepository()
    for i in range(5):
        repo.seed_readable(f"col-{i}", _collection(id=uuid4(), readable_id=f"col-{i}"))

    svc = _build_service(collection_repo=repo)
    result = await svc.list(MagicMock(), ctx=_ctx(), skip=1, limit=2)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_list_search_query_passed_through():
    """list() passes search_query to repo."""
    repo = FakeCollectionRepository()
    repo.seed_readable(
        "finance", _collection(id=uuid4(), name="Finance Data", readable_id="finance")
    )
    repo.seed_readable(
        "marketing",
        _collection(id=uuid4(), name="Marketing", readable_id="marketing"),
    )

    svc = _build_service(collection_repo=repo)
    result = await svc.list(MagicMock(), ctx=_ctx(), search_query="finance")
    assert len(result) == 1


# ---------------------------------------------------------------------------
# count() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_returns_repo_count():
    """count() delegates to repo."""
    repo = FakeCollectionRepository()
    repo.seed_readable("a", _collection(id=uuid4(), readable_id="a"))
    repo.seed_readable("b", _collection(id=uuid4(), readable_id="b"))

    svc = _build_service(collection_repo=repo)
    result = await svc.count(MagicMock(), ctx=_ctx())
    assert result == 2


@pytest.mark.asyncio
async def test_count_search_query_passed_through():
    """count() passes search_query to repo."""
    repo = FakeCollectionRepository()
    repo.seed_readable(
        "finance", _collection(id=uuid4(), name="Finance Data", readable_id="finance")
    )
    repo.seed_readable(
        "marketing",
        _collection(id=uuid4(), name="Marketing", readable_id="marketing"),
    )

    svc = _build_service(collection_repo=repo)
    result = await svc.count(MagicMock(), ctx=_ctx(), search_query="finance")
    assert result == 1


# ---------------------------------------------------------------------------
# create() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_happy_path():
    """create() creates collection, publishes event, tracks analytics."""
    repo = FakeCollectionRepository()
    event_bus = _FakeEventBus()

    svc = _build_service(
        collection_repo=repo,
        event_bus=event_bus,
        settings=_fake_settings(EMBEDDING_DIMENSIONS=3072),
    )

    collection_in = schemas.CollectionCreate(name="New Collection", readable_id="new-collection")

    result = await svc.create(AsyncMock(), collection_in=collection_in, ctx=_ctx())

    assert result is not None
    # Verify event was published
    assert len(event_bus.events) == 1
    assert event_bus.events[0].event_type.value == "collection.created"


@pytest.mark.asyncio
async def test_create_duplicate_raises():
    """create() raises CollectionAlreadyExistsError when readable_id exists."""
    repo = FakeCollectionRepository()
    repo.seed_readable("existing", _collection(readable_id="existing"))

    svc = _build_service(collection_repo=repo)

    collection_in = schemas.CollectionCreate(name="Duplicate", readable_id="existing")

    with pytest.raises(CollectionAlreadyExistsError) as exc_info:
        await svc.create(AsyncMock(), collection_in=collection_in, ctx=_ctx())

    assert exc_info.value.readable_id == "existing"


@pytest.mark.asyncio
async def test_create_sets_embedding_config():
    """create() sets vector_size and embedding_model_name from config."""
    repo = FakeCollectionRepository()
    svc = _build_service(
        collection_repo=repo,
        settings=_fake_settings(EMBEDDING_DIMENSIONS=1536),
    )

    collection_in = schemas.CollectionCreate(name="Embedding Test", readable_id="embed-test")

    await svc.create(AsyncMock(), collection_in=collection_in, ctx=_ctx())

    # Verify repo.create was called with embedding fields
    create_calls = [c for c in repo._calls if c[0] == "create"]
    assert len(create_calls) == 1
    obj_in = create_calls[0][2]  # obj_in dict
    assert obj_in["vector_size"] == 1536
    assert "embedding_model_name" in obj_in


# ---------------------------------------------------------------------------
# get() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_found():
    """get() returns collection when found."""
    repo = FakeCollectionRepository()
    col = _collection()
    repo.seed_readable("test-collection", col)

    svc = _build_service(collection_repo=repo)
    result = await svc.get(MagicMock(), readable_id="test-collection", ctx=_ctx())
    assert result == col


@pytest.mark.asyncio
async def test_get_not_found():
    """get() raises CollectionNotFoundError when not found."""
    svc = _build_service()

    with pytest.raises(CollectionNotFoundError) as exc_info:
        await svc.get(MagicMock(), readable_id="nonexistent", ctx=_ctx())

    assert exc_info.value.readable_id == "nonexistent"


# ---------------------------------------------------------------------------
# update() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_happy_path():
    """update() updates and publishes event."""
    repo = FakeCollectionRepository()
    col = _collection()
    repo.seed_readable("test-collection", col)
    event_bus = _FakeEventBus()

    svc = _build_service(collection_repo=repo, event_bus=event_bus)

    update_in = schemas.CollectionUpdate(name="Updated Name")
    result = await svc.update(
        MagicMock(), readable_id="test-collection", collection_in=update_in, ctx=_ctx()
    )

    assert result is not None
    assert len(event_bus.events) == 1
    assert event_bus.events[0].event_type.value == "collection.updated"


@pytest.mark.asyncio
async def test_update_not_found():
    """update() raises CollectionNotFoundError when not found."""
    svc = _build_service()
    update_in = schemas.CollectionUpdate(name="Updated Name")

    with pytest.raises(CollectionNotFoundError):
        await svc.update(
            MagicMock(), readable_id="nonexistent", collection_in=update_in, ctx=_ctx()
        )


# ---------------------------------------------------------------------------
# delete() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_full_flow():
    """delete() gathers sync IDs, calls teardown, cascade-deletes, publishes event."""
    repo = FakeCollectionRepository()
    sc_repo = FakeSourceConnectionRepository()
    sync_lifecycle = FakeSyncLifecycleService()
    event_bus = _FakeEventBus()

    col = _collection()
    repo.seed_readable("test-collection", col)
    repo.seed(COLLECTION_ID, col)

    sync_id_1 = uuid4()
    sync_id_2 = uuid4()
    sc_repo.seed_sync_ids_for_collection("test-collection", [sync_id_1, sync_id_2])

    svc = _build_service(
        collection_repo=repo,
        sc_repo=sc_repo,
        sync_lifecycle=sync_lifecycle,
        event_bus=event_bus,
    )

    result = await svc.delete(MagicMock(), readable_id="test-collection", ctx=_ctx())

    assert result is not None

    # Verify teardown was called with correct args
    teardown_calls = [c for c in sync_lifecycle._calls if c[0] == "teardown_syncs_for_collection"]
    assert len(teardown_calls) == 1
    _, _, sync_ids, coll_id, org_id, _ = teardown_calls[0]
    assert set(sync_ids) == {sync_id_1, sync_id_2}
    assert coll_id == COLLECTION_ID
    assert org_id == ORG_ID

    # Verify cascade delete was called
    remove_calls = [c for c in repo._calls if c[0] == "remove"]
    assert len(remove_calls) == 1

    # Verify event published
    assert len(event_bus.events) == 1
    assert event_bus.events[0].event_type.value == "collection.deleted"


@pytest.mark.asyncio
async def test_delete_not_found():
    """delete() raises CollectionNotFoundError when not found."""
    svc = _build_service()

    with pytest.raises(CollectionNotFoundError):
        await svc.delete(MagicMock(), readable_id="nonexistent", ctx=_ctx())


@pytest.mark.asyncio
async def test_delete_no_syncs():
    """delete() works when collection has no syncs — teardown called with empty list."""
    repo = FakeCollectionRepository()
    sc_repo = FakeSourceConnectionRepository()
    sync_lifecycle = FakeSyncLifecycleService()
    event_bus = _FakeEventBus()

    col = _collection()
    repo.seed_readable("test-collection", col)
    repo.seed(COLLECTION_ID, col)
    # No sync IDs seeded — empty list

    svc = _build_service(
        collection_repo=repo,
        sc_repo=sc_repo,
        sync_lifecycle=sync_lifecycle,
        event_bus=event_bus,
    )

    result = await svc.delete(MagicMock(), readable_id="test-collection", ctx=_ctx())

    assert result is not None

    teardown_calls = [c for c in sync_lifecycle._calls if c[0] == "teardown_syncs_for_collection"]
    assert len(teardown_calls) == 1
    _, _, sync_ids, _, _, _ = teardown_calls[0]
    assert sync_ids == []
