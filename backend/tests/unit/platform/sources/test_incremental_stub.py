"""Unit tests for IncrementalStubSource with continuous sync."""

import pytest
from unittest.mock import MagicMock

from airweave.platform.entities.stub import SmallStubEntity, StubContainerEntity
from airweave.platform.sources.incremental_stub import IncrementalStubSource


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def source():
    """Create an IncrementalStubSource with defaults."""
    s = IncrementalStubSource()
    s.seed = 42
    s.entity_count = 5
    return s


@pytest.fixture
def source_with_cursor(source):
    """Source with a cursor indicating a previous sync up to index 4."""
    mock_cursor = MagicMock()
    mock_cursor.data = {"last_entity_index": 4, "entity_count": 5}
    source.set_cursor(mock_cursor)
    return source


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_with_config():
    """create() should apply seed and entity_count from config."""
    s = await IncrementalStubSource.create(
        credentials=None,
        config={"seed": 99, "entity_count": 20},
    )
    assert s.seed == 99
    assert s.entity_count == 20


@pytest.mark.asyncio
async def test_create_with_defaults():
    """create() with empty config should use defaults."""
    s = await IncrementalStubSource.create(credentials=None, config=None)
    assert s.seed == 42
    assert s.entity_count == 5


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_returns_true(source):
    """validate() always returns True for stub source."""
    assert await source.validate() is True


# ---------------------------------------------------------------------------
# _generate_entity() determinism
# ---------------------------------------------------------------------------


def test_generate_entity_deterministic(source):
    """Same seed+index should always produce the same entity."""
    e1 = source._generate_entity(0, [])
    e2 = source._generate_entity(0, [])
    assert e1.stub_id == e2.stub_id
    assert e1.title == e2.title
    assert e1.content == e2.content
    assert e1.author == e2.author


def test_generate_entity_different_indices(source):
    """Different indices should produce different entities."""
    e0 = source._generate_entity(0, [])
    e1 = source._generate_entity(1, [])
    assert e0.stub_id != e1.stub_id
    assert e0.stub_id == "inc-stub-42-0"
    assert e1.stub_id == "inc-stub-42-1"


def test_generate_entity_returns_small_stub_entity(source):
    """_generate_entity should return SmallStubEntity with all fields populated."""
    entity = source._generate_entity(3, [])
    assert isinstance(entity, SmallStubEntity)
    assert entity.stub_id == "inc-stub-42-3"
    assert entity.sequence_number == 3
    assert entity.title  # non-empty
    assert entity.content  # non-empty
    assert entity.author  # non-empty
    assert len(entity.tags) == 2
    assert entity.created_at is not None
    assert entity.modified_at is not None


# ---------------------------------------------------------------------------
# generate_entities() — full sync (no cursor)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_sync_yields_container_plus_entities(source):
    """First sync (no cursor) should yield container + entity_count entities."""
    # No cursor set -> full sync
    entities = []
    async for e in source.generate_entities():
        entities.append(e)

    assert len(entities) == 6  # 1 container + 5 data
    assert isinstance(entities[0], StubContainerEntity)
    assert entities[0].container_id == "inc-stub-container-42"

    data_entities = entities[1:]
    for i, e in enumerate(data_entities):
        assert isinstance(e, SmallStubEntity)
        assert e.stub_id == f"inc-stub-42-{i}"


@pytest.mark.asyncio
async def test_full_sync_sets_breadcrumbs(source):
    """Data entities should have the container as a breadcrumb."""
    entities = []
    async for e in source.generate_entities():
        entities.append(e)

    for e in entities[1:]:
        assert len(e.breadcrumbs) == 1
        assert e.breadcrumbs[0].entity_id == "inc-stub-container-42"
        assert e.breadcrumbs[0].entity_type == "StubContainerEntity"


@pytest.mark.asyncio
async def test_full_sync_updates_cursor(source):
    """Full sync should update cursor with last_entity_index and entity_count."""
    mock_cursor = MagicMock()
    mock_cursor.data = {}  # empty cursor -> full sync
    source.set_cursor(mock_cursor)

    async for _ in source.generate_entities():
        pass

    mock_cursor.update.assert_called_once_with(
        last_entity_index=4,
        entity_count=5,
    )


# ---------------------------------------------------------------------------
# generate_entities() — incremental sync (with cursor)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_incremental_sync_only_new_entities(source_with_cursor):
    """Incremental sync should only yield new entities beyond cursor position."""
    source_with_cursor.entity_count = 10  # grew from 5 to 10

    entities = []
    async for e in source_with_cursor.generate_entities():
        entities.append(e)

    # 1 container + 5 new entities (indices 5-9)
    assert len(entities) == 6
    assert isinstance(entities[0], StubContainerEntity)

    data_entities = entities[1:]
    assert len(data_entities) == 5
    for i, e in enumerate(data_entities):
        assert isinstance(e, SmallStubEntity)
        assert e.stub_id == f"inc-stub-42-{i + 5}"


@pytest.mark.asyncio
async def test_incremental_sync_updates_cursor(source_with_cursor):
    """Incremental sync should update cursor to new last_entity_index."""
    source_with_cursor.entity_count = 10

    async for _ in source_with_cursor.generate_entities():
        pass

    source_with_cursor.cursor.update.assert_called_once_with(
        last_entity_index=9,
        entity_count=10,
    )


# ---------------------------------------------------------------------------
# generate_entities() — no-op sync (cursor at end)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_noop_sync_only_container(source_with_cursor):
    """When cursor matches entity_count, only the container is yielded."""
    # cursor at index 4, entity_count=5 -> start_index=5, range(5,5)=empty
    entities = []
    async for e in source_with_cursor.generate_entities():
        entities.append(e)

    assert len(entities) == 1
    assert isinstance(entities[0], StubContainerEntity)


@pytest.mark.asyncio
async def test_noop_sync_still_updates_cursor(source_with_cursor):
    """No-op sync should still update the cursor."""
    async for _ in source_with_cursor.generate_entities():
        pass

    source_with_cursor.cursor.update.assert_called_once_with(
        last_entity_index=4,
        entity_count=5,
    )


# ---------------------------------------------------------------------------
# generate_entities() — no cursor object at all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_cursor_object_full_sync(source):
    """When no cursor is set at all, should do a full sync."""
    # source fixture has no cursor set
    entities = []
    async for e in source.generate_entities():
        entities.append(e)

    assert len(entities) == 6  # container + 5


# ---------------------------------------------------------------------------
# decorator metadata
# ---------------------------------------------------------------------------


def test_source_decorator_metadata():
    """@source decorator should set continuous sync metadata."""
    assert IncrementalStubSource.supports_continuous is True
    assert IncrementalStubSource.short_name == "incremental_stub"
    assert IncrementalStubSource.internal is True
