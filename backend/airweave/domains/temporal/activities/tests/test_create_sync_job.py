"""Tests for CreateSyncJobActivity."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from airweave.adapters.event_bus.fake import FakeEventBus
from airweave.core.exceptions import NotFoundException
from airweave.domains.collections.fakes.repository import FakeCollectionRepository
from airweave.domains.connections.fakes.repository import FakeConnectionRepository
from airweave.domains.source_connections.fakes.repository import FakeSourceConnectionRepository
from airweave.domains.syncs.fakes.sync_job_repository import FakeSyncJobRepository
from airweave.domains.syncs.fakes.sync_repository import FakeSyncRepository
from airweave.domains.temporal.activities.create_sync_job import CreateSyncJobActivity

from .conftest import ORG_ID, SYNC_ID, make_ctx_dict

MODULE = "airweave.domains.temporal.activities.create_sync_job"


@asynccontextmanager
async def _fake_db():
    yield AsyncMock()


def _make_sync_model():
    model = MagicMock()
    model.id = UUID(SYNC_ID)
    model.name = "test-sync"
    model.organization_id = UUID(ORG_ID)
    return model


@pytest.fixture
def event_bus():
    return FakeEventBus()


@pytest.fixture
def sync_repo():
    repo = FakeSyncRepository()
    repo.seed_model(UUID(SYNC_ID), _make_sync_model())
    return repo


@pytest.fixture
def sync_job_repo():
    return FakeSyncJobRepository()


@pytest.fixture
def sc_repo():
    return FakeSourceConnectionRepository()


@pytest.fixture
def conn_repo():
    return FakeConnectionRepository()


@pytest.fixture
def collection_repo():
    return FakeCollectionRepository()


@pytest.fixture
def activity(event_bus, sync_repo, sync_job_repo, sc_repo, conn_repo, collection_repo):
    return CreateSyncJobActivity(
        event_bus=event_bus,
        sync_repo=sync_repo,
        sync_job_repo=sync_job_repo,
        sc_repo=sc_repo,
        conn_repo=conn_repo,
        collection_repo=collection_repo,
    )


@pytest.mark.unit
async def test_creates_sync_job(activity, sync_job_repo):
    with patch(f"{MODULE}.get_db_context", _fake_db):
        result = await activity.run(
            sync_id=SYNC_ID,
            ctx_dict=make_ctx_dict(),
        )

    assert result.sync_job_dict is not None
    assert "id" in result.sync_job_dict
    assert result.orphaned is False
    assert result.skipped is False

    create_calls = [c for c in sync_job_repo._calls if c[0] == "create"]
    assert len(create_calls) == 1


@pytest.mark.unit
async def test_returns_orphaned_when_sync_missing(activity, sync_repo):
    sync_repo._models.clear()

    async def raise_not_found(*args, **kwargs):
        raise NotFoundException("Sync not found")

    sync_repo.get_without_connections = raise_not_found

    with patch(f"{MODULE}.get_db_context", _fake_db):
        result = await activity.run(
            sync_id=SYNC_ID,
            ctx_dict=make_ctx_dict(),
        )

    assert result.orphaned is True
    assert result.reason is not None


@pytest.mark.unit
async def test_skips_when_job_already_running(activity, sync_job_repo):
    running_job = MagicMock()
    running_job.sync_id = UUID(SYNC_ID)
    running_job.organization_id = UUID(ORG_ID)
    running_job.status = "RUNNING"
    sync_job_repo.seed_jobs_for_sync(UUID(SYNC_ID), [running_job])

    with patch(f"{MODULE}.get_db_context", _fake_db):
        result = await activity.run(
            sync_id=SYNC_ID,
            ctx_dict=make_ctx_dict(),
        )

    assert result.skipped is True
    assert result.reason is not None and "Already has" in result.reason


@pytest.mark.unit
async def test_force_full_sync_waits_for_running_jobs(activity, sync_job_repo):
    """force_full_sync=True waits for running jobs then creates a new one."""
    running_job = MagicMock()
    running_job.sync_id = UUID(SYNC_ID)
    running_job.organization_id = UUID(ORG_ID)
    running_job.status = "RUNNING"
    sync_job_repo.seed_jobs_for_sync(UUID(SYNC_ID), [running_job])

    call_count = 0
    original_get_active = sync_job_repo.get_active_for_sync

    async def get_active_declining(db, sync_id, ctx):
        nonlocal call_count
        call_count += 1
        if call_count <= 1:
            return [running_job]
        return []

    sync_job_repo.get_active_for_sync = get_active_declining

    with (
        patch(f"{MODULE}.get_db_context", _fake_db),
        patch(f"{MODULE}.activity") as mock_activity,
        patch(f"{MODULE}.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await activity.run(
            sync_id=SYNC_ID,
            ctx_dict=make_ctx_dict(),
            force_full_sync=True,
        )

    assert result.sync_job_dict is not None
    assert result.orphaned is False
    assert result.skipped is False


@pytest.mark.unit
async def test_force_full_sync_timeout_raises(activity, sync_job_repo):
    """force_full_sync=True raises after timeout when jobs never complete."""
    running_job = MagicMock()
    running_job.sync_id = UUID(SYNC_ID)
    running_job.organization_id = UUID(ORG_ID)
    running_job.status = "RUNNING"
    sync_job_repo.seed_jobs_for_sync(UUID(SYNC_ID), [running_job])

    async def always_running(db, sync_id, ctx):
        return [running_job]

    sync_job_repo.get_active_for_sync = always_running

    with (
        patch(f"{MODULE}.get_db_context", _fake_db),
        patch(f"{MODULE}.activity") as mock_activity,
        patch(f"{MODULE}.asyncio.sleep", new_callable=AsyncMock),
        pytest.raises(Exception, match="Timeout"),
    ):
        await activity.run(
            sync_id=SYNC_ID,
            ctx_dict=make_ctx_dict(),
            force_full_sync=True,
        )


@pytest.mark.unit
async def test_publish_pending_event_success(activity, event_bus, sc_repo, conn_repo, collection_repo):
    """Pending event is published when source connection, connection, and collection are found."""
    from datetime import datetime, timezone

    from airweave.models.connection import Connection
    from airweave.models.source_connection import SourceConnection

    sc = MagicMock(spec=SourceConnection)
    sc.id = UUID("00000000-0000-0000-0000-000000000050")
    sc.connection_id = UUID("00000000-0000-0000-0000-000000000040")
    sc.readable_collection_id = "test-collection"
    sc_repo.seed_by_sync_id(UUID(SYNC_ID), sc)

    conn = MagicMock(spec=Connection)
    conn.id = UUID("00000000-0000-0000-0000-000000000040")
    conn.short_name = "test_source"
    conn_repo.seed(UUID("00000000-0000-0000-0000-000000000040"), conn)

    col = MagicMock()
    col.id = UUID("00000000-0000-0000-0000-000000000030")
    col.name = "test-collection"
    col.readable_id = "test-collection"
    collection_repo.seed_readable("test-collection", col)

    with patch(f"{MODULE}.get_db_context", _fake_db):
        result = await activity.run(
            sync_id=SYNC_ID,
            ctx_dict=make_ctx_dict(),
        )

    assert len(event_bus.events) == 1


@pytest.mark.unit
async def test_publish_pending_event_failure_tolerated(activity, event_bus, sc_repo):
    """publish_pending_event failure is caught and doesn't fail the activity."""

    async def raise_error(*args, **kwargs):
        raise RuntimeError("event bus broken")

    sc_repo.get_by_sync_id = raise_error

    with patch(f"{MODULE}.get_db_context", _fake_db):
        result = await activity.run(
            sync_id=SYNC_ID,
            ctx_dict=make_ctx_dict(),
        )

    assert result.sync_job_dict is not None
    assert len(event_bus.events) == 0
