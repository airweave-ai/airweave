"""Tests for SelfDestructOrphanedSyncActivity."""

import pytest

from airweave.domains.temporal.fakes.schedule_service import FakeTemporalScheduleService
from airweave.domains.temporal.activities.self_destruct_orphaned_sync import (
    SelfDestructOrphanedSyncActivity,
)

from .conftest import SYNC_ID, make_ctx_dict


@pytest.fixture
def schedule_service():
    return FakeTemporalScheduleService()


@pytest.fixture
def activity(schedule_service):
    return SelfDestructOrphanedSyncActivity(temporal_schedule_service=schedule_service)


@pytest.mark.unit
async def test_deletes_all_schedule_types(activity, schedule_service):
    result = await activity.run(
        sync_id=SYNC_ID,
        ctx_dict=make_ctx_dict(),
        reason="Source deleted",
    )

    delete_calls = [c for c in schedule_service._calls if c[0] == "delete_schedule_handle"]
    assert len(delete_calls) == 3
    assert delete_calls[0][1] == f"sync-{SYNC_ID}"
    assert delete_calls[1][1] == f"minute-sync-{SYNC_ID}"
    assert delete_calls[2][1] == f"daily-cleanup-{SYNC_ID}"

    assert len(result["schedules_deleted"]) == 3
    assert result["reason"] == "Source deleted"


@pytest.mark.unit
async def test_tolerates_schedule_not_found(activity, schedule_service):
    schedule_service.set_error(Exception("schedule not found"))

    result = await activity.run(
        sync_id=SYNC_ID,
        ctx_dict=make_ctx_dict(),
    )

    assert result["schedules_deleted"] == []
    assert result["errors"] == []


@pytest.mark.unit
async def test_returns_cleanup_summary(activity):
    result = await activity.run(
        sync_id=SYNC_ID,
        ctx_dict=make_ctx_dict(),
    )

    assert result["sync_id"] == SYNC_ID
    assert "schedules_deleted" in result
    assert "workflows_cancelled" in result
    assert "errors" in result
