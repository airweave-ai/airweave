"""Tests for RunSyncActivity."""

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from temporalio.exceptions import ApplicationError

from airweave import schemas
from airweave.core.context import BaseContext
from airweave.core.exceptions import NotFoundException
from airweave.domains.temporal.activities.run_sync import (
    RunSyncActivity,
    _track_metrics,
)
from airweave.domains.temporal.exceptions import ORPHANED_SYNC_ERROR_TYPE

from .conftest import (
    COLLECTION_ID,
    CONNECTION_ID,
    ORG_ID,
    SYNC_ID,
    SYNC_JOB_ID,
    make_ctx_dict,
)

MODULE = "airweave.domains.temporal.activities.run_sync"


@asynccontextmanager
async def _fake_db():
    yield AsyncMock()


def _make_org():
    return schemas.Organization(
        id=UUID(ORG_ID),
        name="Test Org",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        modified_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


def _make_sync():
    return schemas.Sync(
        id=UUID(SYNC_ID),
        name="test-sync",
        source_connection_id=UUID(CONNECTION_ID),
        destination_connection_ids=[UUID(CONNECTION_ID)],
        organization_id=UUID(ORG_ID),
        status="active",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        modified_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


def _make_sync_job():
    return schemas.SyncJob(
        id=UUID(SYNC_JOB_ID),
        sync_id=UUID(SYNC_ID),
        status="pending",
        organization_id=UUID(ORG_ID),
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        modified_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


def _make_connection():
    return schemas.Connection(
        id=UUID(CONNECTION_ID),
        name="test-conn",
        readable_id="test-conn",
        short_name="test_source",
        integration_type="source",
        status="active",
        organization_id=UUID(ORG_ID),
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        modified_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


VECTOR_DB_METADATA_ID = "00000000-0000-0000-0000-000000000099"


def _make_collection():
    return schemas.CollectionRecord(
        id=UUID(COLLECTION_ID),
        name="test-collection",
        readable_id="test-collection",
        organization_id=UUID(ORG_ID),
        vector_db_deployment_metadata_id=UUID(VECTOR_DB_METADATA_ID),
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        modified_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )


def _make_sync_dict():
    return {
        "id": SYNC_ID,
        "name": "test-sync",
        "source_connection_id": CONNECTION_ID,
        "destination_connection_ids": [CONNECTION_ID],
        "organization_id": ORG_ID,
        "status": "active",
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "modified_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
    }


def _make_sync_job_dict():
    return {
        "id": SYNC_JOB_ID,
        "sync_id": SYNC_ID,
        "status": "pending",
        "organization_id": ORG_ID,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "modified_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
    }


def _make_collection_dict():
    return {
        "id": COLLECTION_ID,
        "name": "test-collection",
        "readable_id": "test-collection",
        "organization_id": ORG_ID,
        "vector_db_deployment_metadata_id": VECTOR_DB_METADATA_ID,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "modified_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
    }


def _make_connection_dict():
    return {
        "id": CONNECTION_ID,
        "name": "test-conn",
        "readable_id": "test-conn",
        "short_name": "test_source",
        "integration_type": "source",
        "status": "active",
        "organization_id": ORG_ID,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "modified_at": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
    }


class FakeSyncService:
    def __init__(self, raise_error: Exception | None = None):
        self._raise_error = raise_error
        self.calls: list[dict] = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        if self._raise_error:
            raise self._raise_error
        return MagicMock()


class FakeSyncRepo:
    def __init__(self, sync_schema=None):
        self._sync = sync_schema

    async def get(self, db, id, ctx):
        return self._sync


class FakeCollectionRepo:
    def __init__(self, collection_model=None):
        self._collection = collection_model

    async def get(self, db, id, ctx):
        return self._collection


# ── _track_metrics() ─────────────────────────────────────────────────


@pytest.mark.unit
async def test_track_metrics_success():
    sync_job = _make_sync_job()
    sync = _make_sync()
    org = _make_org()
    collection = _make_collection()
    connection = _make_connection()
    ctx = BaseContext(organization=org)

    with patch(f"{MODULE}.worker_metrics") as mock_metrics:
        mock_ctx_mgr = AsyncMock()
        mock_metrics.track_activity.return_value = mock_ctx_mgr
        async with _track_metrics(
            sync_job, sync, org, collection, connection, False, ctx
        ):
            pass

    mock_ctx_mgr.__aenter__.assert_awaited_once()
    mock_ctx_mgr.__aexit__.assert_awaited_once()


@pytest.mark.unit
async def test_track_metrics_enter_fails_gracefully():
    sync_job = _make_sync_job()
    sync = _make_sync()
    org = _make_org()
    collection = _make_collection()
    connection = _make_connection()
    ctx = BaseContext(organization=org)

    with patch(f"{MODULE}.worker_metrics") as mock_metrics:
        mock_ctx_mgr = AsyncMock()
        mock_ctx_mgr.__aenter__.side_effect = RuntimeError("metrics broken")
        mock_metrics.track_activity.return_value = mock_ctx_mgr
        async with _track_metrics(
            sync_job, sync, org, collection, connection, False, ctx
        ):
            pass

    mock_ctx_mgr.__aexit__.assert_not_awaited()


# ── RunSyncActivity.run() ───────────────────────────────────────────


@pytest.mark.unit
async def test_run_sync_happy_path():
    sync_service = FakeSyncService()
    sync_repo = FakeSyncRepo(sync_schema=_make_sync())
    collection_model = MagicMock()
    collection_model.id = UUID(COLLECTION_ID)
    collection_model.name = "test-collection"
    collection_model.readable_id = "test-collection"
    collection_model.organization_id = UUID(ORG_ID)
    collection_model.vector_db_deployment_metadata_id = UUID(VECTOR_DB_METADATA_ID)
    collection_model.sync_config = None
    collection_model.created_by_email = None
    collection_model.modified_by_email = None
    collection_model.status = "ACTIVE"
    collection_model.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    collection_model.modified_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    collection_repo = FakeCollectionRepo(collection_model=collection_model)

    activity = RunSyncActivity(
        sync_service=sync_service,
        sync_repo=sync_repo,
        collection_repo=collection_repo,
    )

    with (
        patch(f"{MODULE}.get_db_context", _fake_db),
        patch(f"{MODULE}.worker_metrics") as mock_metrics,
        patch.object(activity, "_execute_with_heartbeat", new_callable=AsyncMock),
    ):
        mock_ctx_mgr = AsyncMock()
        mock_metrics.track_activity.return_value = mock_ctx_mgr
        await activity.run(
            sync_dict=_make_sync_dict(),
            sync_job_dict=_make_sync_job_dict(),
            collection_dict=_make_collection_dict(),
            connection_dict=_make_connection_dict(),
            ctx_dict=make_ctx_dict(),
        )


# ── _resolve_from_db() ──────────────────────────────────────────────


@pytest.mark.unit
async def test_resolve_from_db_sync_not_found():
    sync_repo = FakeSyncRepo(sync_schema=None)
    collection_repo = FakeCollectionRepo()

    activity = RunSyncActivity(
        sync_service=MagicMock(),
        sync_repo=sync_repo,
        collection_repo=collection_repo,
    )

    ctx = BaseContext(organization=_make_org())
    with (
        patch(f"{MODULE}.get_db_context", _fake_db),
        pytest.raises(ValueError, match="not found"),
    ):
        await activity._resolve_from_db(
            _make_sync_dict(), _make_collection_dict(), ctx
        )


@pytest.mark.unit
async def test_resolve_from_db_collection_not_found():
    sync_repo = FakeSyncRepo(sync_schema=_make_sync())
    collection_repo = FakeCollectionRepo(collection_model=None)

    activity = RunSyncActivity(
        sync_service=MagicMock(),
        sync_repo=sync_repo,
        collection_repo=collection_repo,
    )

    ctx = BaseContext(organization=_make_org())
    with (
        patch(f"{MODULE}.get_db_context", _fake_db),
        pytest.raises(ValueError, match="Collection .* not found"),
    ):
        await activity._resolve_from_db(
            _make_sync_dict(), _make_collection_dict(), ctx
        )


# ── _run_sync() ─────────────────────────────────────────────────────


@pytest.mark.unit
async def test_run_sync_orphaned_sync_error():
    sync_service = FakeSyncService(
        raise_error=NotFoundException("Source connection record not found")
    )
    activity = RunSyncActivity(
        sync_service=sync_service,
        sync_repo=MagicMock(),
        collection_repo=MagicMock(),
    )

    ctx = BaseContext(organization=_make_org())
    sync_job = _make_sync_job()

    with (
        patch(f"{MODULE}.get_db_context", _fake_db),
        patch(f"{MODULE}.crud") as mock_crud,
        pytest.raises(ApplicationError) as exc_info,
    ):
        mock_crud.sync_job.get.return_value = None
        await activity._run_sync(
            _make_sync(),
            sync_job,
            _make_collection(),
            _make_connection(),
            ctx,
        )

    assert exc_info.value.type == ORPHANED_SYNC_ERROR_TYPE


@pytest.mark.unit
async def test_run_sync_non_orphan_not_found_error_propagates():
    sync_service = FakeSyncService(
        raise_error=NotFoundException("Some other not found error")
    )
    activity = RunSyncActivity(
        sync_service=sync_service,
        sync_repo=MagicMock(),
        collection_repo=MagicMock(),
    )

    ctx = BaseContext(organization=_make_org())

    with (
        patch(f"{MODULE}.get_db_context", _fake_db),
        patch(f"{MODULE}.crud") as mock_crud,
        pytest.raises(NotFoundException, match="Some other not found"),
    ):
        mock_crud.sync_job.get.return_value = None
        await activity._run_sync(
            _make_sync(),
            _make_sync_job(),
            _make_collection(),
            _make_connection(),
            ctx,
        )


# ── _load_execution_config() ────────────────────────────────────────


@pytest.mark.unit
async def test_load_execution_config_with_config():
    activity = RunSyncActivity(
        sync_service=MagicMock(),
        sync_repo=MagicMock(),
        collection_repo=MagicMock(),
    )

    ctx = BaseContext(organization=_make_org())
    sync_job = _make_sync_job()

    mock_model = MagicMock()
    mock_model.sync_config = {"handlers": {"enable_postgres_handler": True}}
    mock_crud = MagicMock()
    mock_crud.sync_job.get = AsyncMock(return_value=mock_model)

    with (
        patch(f"{MODULE}.get_db_context", _fake_db),
        patch(f"{MODULE}.crud", mock_crud),
    ):
        result = await activity._load_execution_config(sync_job, ctx)

    assert result is not None


@pytest.mark.unit
async def test_load_execution_config_failure_returns_none():
    activity = RunSyncActivity(
        sync_service=MagicMock(),
        sync_repo=MagicMock(),
        collection_repo=MagicMock(),
    )

    ctx = BaseContext(organization=_make_org())
    sync_job = _make_sync_job()

    with (
        patch(f"{MODULE}.get_db_context", side_effect=RuntimeError("db error")),
    ):
        result = await activity._load_execution_config(sync_job, ctx)

    assert result is None


@pytest.mark.unit
async def test_load_execution_config_no_model():
    activity = RunSyncActivity(
        sync_service=MagicMock(),
        sync_repo=MagicMock(),
        collection_repo=MagicMock(),
    )

    ctx = BaseContext(organization=_make_org())
    sync_job = _make_sync_job()

    mock_crud = MagicMock()
    mock_crud.sync_job.get = AsyncMock(return_value=None)

    with (
        patch(f"{MODULE}.get_db_context", _fake_db),
        patch(f"{MODULE}.crud", mock_crud),
    ):
        result = await activity._load_execution_config(sync_job, ctx)

    assert result is None


# ── _execute_with_heartbeat() ────────────────────────────────────────


@pytest.mark.unit
async def test_execute_with_heartbeat_cancellation_drains_task():
    act = RunSyncActivity(
        sync_service=MagicMock(),
        sync_repo=MagicMock(),
        collection_repo=MagicMock(),
    )

    sync = _make_sync()
    sync_job = _make_sync_job()
    ctx = BaseContext(organization=_make_org())

    with (
        patch.object(act, "_run_sync", new_callable=AsyncMock),
        patch(f"{MODULE}.HeartbeatMonitor") as mock_monitor_cls,
        patch.object(act, "_drain_task", new_callable=AsyncMock),
        pytest.raises(asyncio.CancelledError),
    ):
        mock_monitor = AsyncMock()
        mock_monitor.run.side_effect = asyncio.CancelledError()
        mock_monitor_cls.return_value = mock_monitor

        await act._execute_with_heartbeat(
            sync, sync_job, _make_collection(), _make_connection(), ctx, None, False
        )


# ── _drain_task() ────────────────────────────────────────────────────


@pytest.mark.unit
async def test_drain_task_cancels_and_heartbeats():
    act = RunSyncActivity(
        sync_service=MagicMock(),
        sync_repo=MagicMock(),
        collection_repo=MagicMock(),
    )

    ctx = BaseContext(organization=_make_org())
    completed = False

    async def slow_cancel():
        nonlocal completed
        try:
            await asyncio.sleep(100)
        except asyncio.CancelledError:
            completed = True
            raise

    task = asyncio.create_task(slow_cancel())
    await asyncio.sleep(0)

    with patch(f"{MODULE}.activity") as mock_activity:
        with suppress(asyncio.CancelledError):
            await act._drain_task(ctx, task)

    assert completed
    assert task.done()


@pytest.mark.unit
async def test_drain_task_heartbeats_on_timeout():
    """_drain_task emits heartbeats when waiting for a slow task cancellation."""
    act = RunSyncActivity(
        sync_service=MagicMock(),
        sync_repo=MagicMock(),
        collection_repo=MagicMock(),
    )

    ctx = BaseContext(organization=_make_org())
    finish = asyncio.Event()

    async def stubborn():
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            await finish.wait()

    task = asyncio.create_task(stubborn())
    await asyncio.sleep(0)

    call_count = 0

    async def mock_wait_for(aw, *, timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise asyncio.TimeoutError()
        finish.set()
        await asyncio.sleep(0)

    with (
        patch.object(asyncio, "wait_for", mock_wait_for),
        patch(f"{MODULE}.activity") as mock_act,
    ):
        await act._drain_task(ctx, task)

    assert mock_act.heartbeat.call_count == 1
    mock_act.heartbeat.assert_called_with({"phase": "cancelling"})
