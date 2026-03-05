"""Unit tests for SourceConnectionDeletionService.

Table-driven tests covering:
- Happy paths: no sync, completed job, running/cancelling/pending jobs
- Error paths: not found, collection not found, cancel failure, cleanup failure, timeout
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import airweave.domains.source_connections.delete as delete_module
from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import logger
from airweave.core.shared_models import AuthMethod, SyncJobStatus
from airweave.domains.collections.fakes.repository import FakeCollectionRepository
from airweave.domains.source_connections.delete import SourceConnectionDeletionService
from airweave.domains.source_connections.fakes.repository import (
    FakeSourceConnectionRepository,
)
from airweave.domains.source_connections.fakes.response import FakeResponseBuilder
from airweave.domains.syncs.fakes.sync_job_repository import FakeSyncJobRepository
from airweave.domains.syncs.fakes.sync_lifecycle_service import FakeSyncLifecycleService
from airweave.domains.temporal.fakes.service import FakeTemporalWorkflowService
from airweave.models.collection import Collection
from airweave.models.source_connection import SourceConnection
from airweave.models.sync_job import SyncJob
from airweave.schemas.organization import Organization
from airweave.schemas.source_connection import SourceConnectionJob

NOW = datetime.now(timezone.utc)
ORG_ID = uuid4()
COLLECTION_ID = uuid4()


def _make_ctx() -> ApiContext:
    org = Organization(id=str(ORG_ID), name="Test Org", created_at=NOW, modified_at=NOW)
    return ApiContext(
        request_id="test-req",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        logger=logger.with_context(request_id="test-req"),
    )


def _make_sc(*, id=None, sync_id=None, readable_collection_id="test-col", name="Test SC", short_name="github"):
    sc = MagicMock(spec=SourceConnection)
    sc.id = id or uuid4()
    sc.sync_id = sync_id
    sc.readable_collection_id = readable_collection_id
    sc.name = name
    sc.short_name = short_name
    sc.organization_id = ORG_ID
    sc.description = None
    sc.is_authenticated = True
    sc.created_at = NOW
    sc.modified_at = NOW
    return sc


def _make_collection(*, id=None, readable_id="test-col"):
    col = MagicMock(spec=Collection)
    col.id = id or COLLECTION_ID
    col.readable_id = readable_id
    col.organization_id = ORG_ID
    return col


def _make_job(*, status=SyncJobStatus.COMPLETED, sync_id=None):
    job = MagicMock(spec=SyncJob)
    job.id = uuid4()
    job.sync_id = sync_id or uuid4()
    job.status = status
    return job


def _build_service(
    sc_repo=None,
    collection_repo=None,
    sync_job_repo=None,
    sync_lifecycle=None,
    response_builder=None,
    temporal_workflow_service=None,
):
    return SourceConnectionDeletionService(
        sc_repo=sc_repo or FakeSourceConnectionRepository(),
        collection_repo=collection_repo or FakeCollectionRepository(),
        sync_job_repo=sync_job_repo or FakeSyncJobRepository(),
        sync_lifecycle=sync_lifecycle or FakeSyncLifecycleService(),
        response_builder=response_builder or FakeResponseBuilder(),
        temporal_workflow_service=temporal_workflow_service or FakeTemporalWorkflowService(),
    )


# ---------------------------------------------------------------------------
# Happy paths -- table-driven
# ---------------------------------------------------------------------------


@dataclass
class DeleteCase:
    desc: str
    has_sync: bool
    job_status: Optional[SyncJobStatus]
    expect_cancel: bool
    expect_wait: bool
    expect_cleanup: bool


DELETE_CASES = [
    DeleteCase("no_sync", has_sync=False, job_status=None, expect_cancel=False, expect_wait=False, expect_cleanup=False),
    DeleteCase("sync_no_running_job", has_sync=True, job_status=SyncJobStatus.COMPLETED, expect_cancel=False, expect_wait=False, expect_cleanup=True),
    DeleteCase("running_job", has_sync=True, job_status=SyncJobStatus.RUNNING, expect_cancel=True, expect_wait=True, expect_cleanup=True),
    DeleteCase("cancelling_job", has_sync=True, job_status=SyncJobStatus.CANCELLING, expect_cancel=False, expect_wait=True, expect_cleanup=True),
    DeleteCase("pending_job", has_sync=True, job_status=SyncJobStatus.PENDING, expect_cancel=True, expect_wait=True, expect_cleanup=True),
]


@pytest.mark.parametrize("case", DELETE_CASES, ids=lambda c: c.desc)
async def test_delete_happy_path(case: DeleteCase):
    sync_id = uuid4() if case.has_sync else None
    sc = _make_sc(sync_id=sync_id)
    col = _make_collection()

    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)
    col_repo = FakeCollectionRepository()
    col_repo.seed_readable(sc.readable_collection_id, col)

    job_repo = FakeSyncJobRepository()
    if case.job_status is not None and sync_id:
        job_repo.seed_last_job(sync_id, _make_job(status=case.job_status, sync_id=sync_id))

    lifecycle = FakeSyncLifecycleService()
    if case.expect_cancel:
        lifecycle.set_cancel_result(MagicMock(spec=SourceConnectionJob))

    temporal = FakeTemporalWorkflowService()

    svc = _build_service(
        sc_repo=sc_repo,
        collection_repo=col_repo,
        sync_job_repo=job_repo,
        sync_lifecycle=lifecycle,
        temporal_workflow_service=temporal,
    )

    if case.expect_wait:
        svc._wait_for_sync_job_terminal_state = AsyncMock(return_value=True)

    result = await svc.delete(AsyncMock(), id=sc.id, ctx=_make_ctx())

    assert result.id == sc.id
    assert sc_repo._store.get(sc.id) is None

    if case.expect_cancel:
        assert any(c[0] == "cancel_job" for c in lifecycle._calls)
    if case.expect_wait:
        svc._wait_for_sync_job_terminal_state.assert_awaited_once()
    if case.expect_cleanup:
        assert any(c[0] == "start_cleanup_sync_data_workflow" for c in temporal._calls)


# ---------------------------------------------------------------------------
# Error paths -- table-driven
# ---------------------------------------------------------------------------


@dataclass
class DeleteErrorCase:
    desc: str
    seed_sc: bool
    seed_collection: bool
    expect_exception: type
    expect_match: str


DELETE_ERROR_CASES = [
    DeleteErrorCase("not_found", seed_sc=False, seed_collection=False, expect_exception=NotFoundException, expect_match="Source connection not found"),
    DeleteErrorCase("collection_not_found", seed_sc=True, seed_collection=False, expect_exception=NotFoundException, expect_match="Collection not found"),
]


@pytest.mark.parametrize("case", DELETE_ERROR_CASES, ids=lambda c: c.desc)
async def test_delete_error(case: DeleteErrorCase):
    sc = _make_sc()
    sc_repo = FakeSourceConnectionRepository()
    col_repo = FakeCollectionRepository()

    if case.seed_sc:
        sc_repo.seed(sc.id, sc)
    if case.seed_collection:
        col_repo.seed_readable(sc.readable_collection_id, _make_collection())

    svc = _build_service(sc_repo=sc_repo, collection_repo=col_repo)

    with pytest.raises(case.expect_exception, match=case.expect_match):
        await svc.delete(AsyncMock(), id=sc.id, ctx=_make_ctx())


async def test_delete_cancel_failure_is_swallowed():
    """Cancel failure during delete is warned but not re-raised."""
    sync_id = uuid4()
    sc = _make_sc(sync_id=sync_id)
    col = _make_collection()

    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)
    col_repo = FakeCollectionRepository()
    col_repo.seed_readable(sc.readable_collection_id, col)

    running_job = _make_job(status=SyncJobStatus.RUNNING, sync_id=sync_id)
    job_repo = FakeSyncJobRepository()
    job_repo.seed_last_job(sync_id, running_job)

    lifecycle = FakeSyncLifecycleService()
    lifecycle.set_error(RuntimeError("cancel boom"))
    temporal = FakeTemporalWorkflowService()

    svc = _build_service(
        sc_repo=sc_repo,
        collection_repo=col_repo,
        sync_job_repo=job_repo,
        sync_lifecycle=lifecycle,
        temporal_workflow_service=temporal,
    )
    svc._wait_for_sync_job_terminal_state = AsyncMock(return_value=True)

    result = await svc.delete(AsyncMock(), id=sc.id, ctx=_make_ctx())
    assert result.id == sc.id


async def test_delete_temporal_cleanup_failure_is_logged():
    """Temporal cleanup failure is logged but not re-raised."""
    sync_id = uuid4()
    sc = _make_sc(sync_id=sync_id)
    col = _make_collection()

    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)
    col_repo = FakeCollectionRepository()
    col_repo.seed_readable(sc.readable_collection_id, col)

    job_repo = FakeSyncJobRepository()
    completed_job = _make_job(status=SyncJobStatus.COMPLETED, sync_id=sync_id)
    job_repo.seed_last_job(sync_id, completed_job)

    temporal = FakeTemporalWorkflowService()
    temporal.set_error(RuntimeError("cleanup boom"))

    svc = _build_service(
        sc_repo=sc_repo,
        collection_repo=col_repo,
        sync_job_repo=job_repo,
        temporal_workflow_service=temporal,
    )
    result = await svc.delete(AsyncMock(), id=sc.id, ctx=_make_ctx())
    assert result.id == sc.id


async def test_delete_wait_timeout_proceeds():
    """If wait_for_terminal_state returns False, deletion still proceeds."""
    sync_id = uuid4()
    sc = _make_sc(sync_id=sync_id)
    col = _make_collection()

    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)
    col_repo = FakeCollectionRepository()
    col_repo.seed_readable(sc.readable_collection_id, col)

    running_job = _make_job(status=SyncJobStatus.RUNNING, sync_id=sync_id)
    job_repo = FakeSyncJobRepository()
    job_repo.seed_last_job(sync_id, running_job)

    lifecycle = FakeSyncLifecycleService()
    lifecycle.set_cancel_result(MagicMock(spec=SourceConnectionJob))
    temporal = FakeTemporalWorkflowService()

    svc = _build_service(
        sc_repo=sc_repo,
        collection_repo=col_repo,
        sync_job_repo=job_repo,
        sync_lifecycle=lifecycle,
        temporal_workflow_service=temporal,
    )
    svc._wait_for_sync_job_terminal_state = AsyncMock(return_value=False)

    result = await svc.delete(AsyncMock(), id=sc.id, ctx=_make_ctx())
    assert result.id == sc.id
    assert sc_repo._store.get(sc.id) is None


async def test_wait_for_sync_job_terminal_state_reaches_terminal(monkeypatch):
    sync_id = uuid4()
    running_job = _make_job(status=SyncJobStatus.RUNNING, sync_id=sync_id)
    cancelled_job = _make_job(status=SyncJobStatus.CANCELLED, sync_id=sync_id)

    job_repo = FakeSyncJobRepository()
    job_repo.get_latest_by_sync_id = AsyncMock(side_effect=[running_job, cancelled_job])  # type: ignore[method-assign]
    svc = _build_service(sync_job_repo=job_repo)

    async def _no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(delete_module.asyncio, "sleep", _no_sleep)

    db = MagicMock()
    db.expire_all = MagicMock()

    reached = await svc._wait_for_sync_job_terminal_state(
        db, sync_id, timeout_seconds=2, poll_interval=1
    )

    assert reached is True
    assert db.expire_all.call_count == 2


async def test_wait_for_sync_job_terminal_state_times_out(monkeypatch):
    sync_id = uuid4()
    running_job = _make_job(status=SyncJobStatus.RUNNING, sync_id=sync_id)

    job_repo = FakeSyncJobRepository()
    job_repo.get_latest_by_sync_id = AsyncMock(side_effect=[running_job, running_job])  # type: ignore[method-assign]
    svc = _build_service(sync_job_repo=job_repo)

    async def _no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(delete_module.asyncio, "sleep", _no_sleep)

    db = MagicMock()
    db.expire_all = MagicMock()

    reached = await svc._wait_for_sync_job_terminal_state(
        db, sync_id, timeout_seconds=2, poll_interval=1
    )

    assert reached is False
    assert db.expire_all.call_count == 2
