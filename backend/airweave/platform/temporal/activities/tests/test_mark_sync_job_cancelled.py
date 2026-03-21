"""Tests for MarkSyncJobCancelledActivity."""

import pytest

from airweave.core.shared_models import SyncJobStatus
from airweave.domains.syncs.fakes.sync_job_service import FakeSyncJobService
from airweave.platform.temporal.activities.mark_sync_job_cancelled import (
    MarkSyncJobCancelledActivity,
)

from .conftest import SYNC_JOB_ID, make_ctx_dict


@pytest.fixture
def sync_job_service():
    return FakeSyncJobService()


@pytest.fixture
def activity(sync_job_service):
    return MarkSyncJobCancelledActivity(sync_job_service=sync_job_service)


@pytest.mark.unit
async def test_marks_job_cancelled(activity, sync_job_service):
    await activity.run(
        sync_job_id=SYNC_JOB_ID,
        ctx_dict=make_ctx_dict(),
        reason="User requested cancellation",
    )

    assert len(sync_job_service._calls) == 1
    call = sync_job_service._calls[0]
    assert call[0] == "update_status"
    assert call[2] == SyncJobStatus.CANCELLED
    assert call[5] == "User requested cancellation"


@pytest.mark.unit
async def test_marks_job_cancelled_with_timestamp(activity, sync_job_service):
    await activity.run(
        sync_job_id=SYNC_JOB_ID,
        ctx_dict=make_ctx_dict(),
        reason="Timeout",
        when_iso="2025-01-15T10:30:00",
    )

    call = sync_job_service._calls[0]
    assert call[8] is not None  # failed_at
    assert call[8].year == 2025


@pytest.mark.unit
async def test_marks_job_cancelled_without_reason(activity, sync_job_service):
    await activity.run(
        sync_job_id=SYNC_JOB_ID,
        ctx_dict=make_ctx_dict(),
    )

    call = sync_job_service._calls[0]
    assert call[5] is None  # error=None
    assert call[8] is None  # failed_at=None


@pytest.mark.unit
async def test_propagates_service_error(activity, sync_job_service):
    sync_job_service.set_error(RuntimeError("db down"))

    with pytest.raises(RuntimeError, match="db down"):
        await activity.run(
            sync_job_id=SYNC_JOB_ID,
            ctx_dict=make_ctx_dict(),
        )
