"""Unit tests for FakeSourceConnectionRepository.

Tests the fake implementation to ensure it behaves correctly for
downstream service tests that depend on it.
"""

from uuid import uuid4

import pytest

from airweave.domains.source_connections.fake_repository import FakeSourceConnectionRepository


def _make_sc(
    *,
    id=None,
    name="Test Connection",
    short_name="stripe",
    readable_collection_id="col-123",
    is_authenticated=True,
    connection_init_session_id=None,
):
    """Build a fake source connection object."""
    return type("FakeSC", (), {
        "id": id or uuid4(),
        "name": name,
        "short_name": short_name,
        "readable_collection_id": readable_collection_id,
        "is_authenticated": is_authenticated,
        "connection_init_session_id": connection_init_session_id,
        "created_at": None,
        "modified_at": None,
    })()


class TestGet:
    @pytest.mark.asyncio
    async def test_get_existing(self):
        repo = FakeSourceConnectionRepository()
        sc = _make_sc()
        repo.seed(sc)
        result = await repo.get(None, id=sc.id, ctx=None)
        assert result is sc

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self):
        repo = FakeSourceConnectionRepository()
        result = await repo.get(None, id=uuid4(), ctx=None)
        assert result is None


class TestGetMultiWithStats:
    @pytest.mark.asyncio
    async def test_returns_stat_dicts(self):
        repo = FakeSourceConnectionRepository()
        repo.seed(_make_sc(name="A"), _make_sc(name="B"))
        results = await repo.get_multi_with_stats(
            None, ctx=None, collection_id=None, skip=0, limit=10
        )
        assert len(results) == 2
        assert all("id" in r for r in results)
        assert all("short_name" in r for r in results)

    @pytest.mark.asyncio
    async def test_filters_by_collection(self):
        repo = FakeSourceConnectionRepository()
        repo.seed(
            _make_sc(readable_collection_id="col-a"),
            _make_sc(readable_collection_id="col-b"),
        )
        results = await repo.get_multi_with_stats(
            None, ctx=None, collection_id="col-a", skip=0, limit=10
        )
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_pagination(self):
        repo = FakeSourceConnectionRepository()
        for _ in range(5):
            repo.seed(_make_sc())
        results = await repo.get_multi_with_stats(
            None, ctx=None, collection_id=None, skip=2, limit=2
        )
        assert len(results) == 2


class TestGetByQueryAndOrg:
    @pytest.mark.asyncio
    async def test_finds_by_attribute(self):
        repo = FakeSourceConnectionRepository()
        session_id = uuid4()
        sc = _make_sc(connection_init_session_id=session_id)
        repo.seed(sc)
        result = await repo.get_by_query_and_org(
            None, ctx=None, connection_init_session_id=session_id
        )
        assert result is sc

    @pytest.mark.asyncio
    async def test_returns_none_when_no_match(self):
        repo = FakeSourceConnectionRepository()
        repo.seed(_make_sc())
        result = await repo.get_by_query_and_org(
            None, ctx=None, connection_init_session_id=uuid4()
        )
        assert result is None


class TestCreate:
    @pytest.mark.asyncio
    async def test_creates_and_stores(self):
        repo = FakeSourceConnectionRepository()
        result = await repo.create(None, obj_in={"name": "New"}, ctx=None, uow=None)
        assert result.id is not None
        assert result.name == "New"
        assert repo.created_count == 1


class TestRemove:
    @pytest.mark.asyncio
    async def test_removes_from_store(self):
        repo = FakeSourceConnectionRepository()
        sc = _make_sc()
        repo.seed(sc)
        await repo.remove(None, id=sc.id, ctx=None)
        assert await repo.get(None, id=sc.id, ctx=None) is None
        assert sc.id in repo._removed

    @pytest.mark.asyncio
    async def test_remove_nonexistent_returns_none(self):
        repo = FakeSourceConnectionRepository()
        result = await repo.remove(None, id=uuid4(), ctx=None)
        assert result is None


class TestUpdate:
    @pytest.mark.asyncio
    async def test_updates_fields(self):
        repo = FakeSourceConnectionRepository()
        sc = _make_sc(name="Old")
        repo.seed(sc)
        await repo.update(None, db_obj=sc, obj_in={"name": "New"}, ctx=None, uow=None)
        assert sc.name == "New"
