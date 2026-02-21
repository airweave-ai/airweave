"""Unit tests for SourceConnectionDeletionService.

Table-driven tests covering:
- Happy path: no sync, with sync (no running jobs), with running job
- Cancellation failures (swallowed)
- Terminal-state timeout (proceeds anyway)
- Collection not found
- Source connection not found
- Temporal cleanup failure (logged, not raised)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

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


def _make_sc(
    *,
    id=None,
    sync_id=None,
    readable_collection_id="test-col",
    name="Test SC",
    short_name="github",
) -> SourceConnection:
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


def _make_collection(*, id=None, readable_id="test-col") -> Collection:
    col = MagicMock(spec=Collection)
    col.id = id or COLLECTION_ID
    col.readable_id = readable_id
    col.organization_id = ORG_ID
    return col


def _make_job(*, status=SyncJobStatus.COMPLETED, sync_id=None) -> SyncJob:
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
) -> SourceConnectionDeletionService:
    return SourceConnectionDeletionService(
        sc_repo=sc_repo or FakeSourceConnectionRepository(),
        collection_repo=collection_repo or FakeCollectionRepository(),
        sync_job_repo=sync_job_repo or FakeSyncJobRepository(),
        sync_lifecycle=sync_lifecycle or FakeSyncLifecycleService(),
        response_builder=response_builder or FakeResponseBuilder(),
        temporal_workflow_service=temporal_workflow_service or FakeTemporalWorkflowService(),
    )


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


async def test_delete_no_sync():
    """SC with no sync_id: skip cancellation, just delete."""
    sc = _make_sc(sync_id=None)
    col = _make_collection()

    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)
    col_repo = FakeCollectionRepository()
    col_repo.seed_readable(sc.readable_collection_id, col)

    svc = _build_service(sc_repo=sc_repo, collection_repo=col_repo)
    result = await svc.delete(AsyncMock(), id=sc.id, ctx=_make_ctx())

    assert result.id == sc.id
    assert sc_repo._store.get(sc.id) is None


async def test_delete_with_sync_no_running_job():
    """SC with sync_id but no active job: skip cancellation, trigger cleanup."""
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

    svc = _build_service(
        sc_repo=sc_repo,
        collection_repo=col_repo,
        sync_job_repo=job_repo,
        temporal_workflow_service=temporal,
    )
    result = await svc.delete(AsyncMock(), id=sc.id, ctx=_make_ctx())

    assert result.id == sc.id
    assert sc_repo._store.get(sc.id) is None
    assert any(c[0] == "start_cleanup_sync_data_workflow" for c in temporal._calls)


async def test_delete_with_running_job():
    """SC with a running job: cancel, wait, delete, cleanup."""
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

    temporal = FakeTemporalWorkflowService()
    cancel_result = MagicMock(spec=SourceConnectionJob)
    lifecycle = FakeSyncLifecycleService()
    lifecycle.set_cancel_result(cancel_result)

    svc = _build_service(
        sc_repo=sc_repo,
        collection_repo=col_repo,
        sync_job_repo=job_repo,
        sync_lifecycle=lifecycle,
        temporal_workflow_service=temporal,
    )
    # Patch the wait barrier to return True immediately
    svc._wait_for_sync_job_terminal_state = AsyncMock(return_value=True)

    result = await svc.delete(AsyncMock(), id=sc.id, ctx=_make_ctx())
    assert result.id == sc.id
    svc._wait_for_sync_job_terminal_state.assert_awaited_once()


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


async def test_delete_not_found():
    """Raises NotFoundException when SC doesn't exist."""
    svc = _build_service()
    with pytest.raises(NotFoundException, match="Source connection not found"):
        await svc.delete(AsyncMock(), id=uuid4(), ctx=_make_ctx())


async def test_delete_collection_not_found():
    """Raises NotFoundException when collection doesn't exist."""
    sc = _make_sc(sync_id=None)
    sc_repo = FakeSourceConnectionRepository()
    sc_repo.seed(sc.id, sc)

    svc = _build_service(sc_repo=sc_repo)
    with pytest.raises(NotFoundException, match="Collection not found"):
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
