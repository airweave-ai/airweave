"""Tests for CleanupStuckSyncJobsActivity."""

import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from airweave.core.shared_models import SyncJobStatus
from airweave.domains.temporal.activities.cleanup_stuck_sync_jobs import (
    CleanupStuckSyncJobsActivity,
    _CANCELLING_PENDING_CUTOFF,
    _REDIS_SNAPSHOT_KEY_PREFIX,
    _RUNNING_CUTOFF,
    _STUCK_CANCEL_REASON,
    _STUCK_RUNNING_REASON,
)

from .conftest import ORG_ID, SYNC_ID, SYNC_JOB_ID

MODULE = "airweave.domains.temporal.activities.cleanup_stuck_sync_jobs"


@asynccontextmanager
async def _fake_db():
    yield AsyncMock()


def _mock_redis(mock_inner):
    """Build a redis_client replacement whose .client attr is the given mock."""
    rc = MagicMock()
    rc.client = mock_inner
    return rc


def _make_job(
    job_id: str = SYNC_JOB_ID,
    sync_id: str = SYNC_ID,
    org_id: str = ORG_ID,
    status: str = "cancelling",
    sync_config: dict | None = None,
) -> MagicMock:
    job = MagicMock()
    job.id = UUID(job_id)
    job.sync_id = UUID(sync_id)
    job.organization_id = UUID(org_id)
    job.status = status
    job.sync_config = sync_config
    return job


def _make_org(org_id: str = ORG_ID):
    """Create a proper Organization ORM-like model that Pydantic can validate."""
    from datetime import timezone

    from airweave.models.organization import Organization

    org = MagicMock(spec=Organization)
    org.id = UUID(org_id)
    org.name = "Test Org"
    org.description = None
    org.auth0_org_id = None
    org.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    org.modified_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    org.billing = None
    org.org_metadata = None
    return org


class FakeStateMachine:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def transition(self, *, sync_job_id, target, ctx, error=None, **kwargs):
        self.calls.append(
            {"sync_job_id": sync_job_id, "target": target, "error": error}
        )
        return MagicMock(applied=True)


class FakeTemporalWorkflowService:
    def __init__(self, cancel_result: bool = True) -> None:
        self._cancel_result = cancel_result
        self.calls: list[tuple] = []

    async def cancel_sync_job_workflow(self, sync_job_id, ctx):
        self.calls.append(("cancel", sync_job_id))
        return self._cancel_result


@pytest.fixture
def state_machine():
    return FakeStateMachine()


@pytest.fixture
def workflow_service():
    return FakeTemporalWorkflowService()


@pytest.fixture
def act(workflow_service, state_machine):
    return CleanupStuckSyncJobsActivity(
        temporal_workflow_service=workflow_service,
        state_machine=state_machine,
    )


# ── run() ────────────────────────────────────────────────────────────


@pytest.mark.unit
async def test_run_no_stuck_jobs(act):
    mock_crud = MagicMock()
    mock_crud.sync_job.get_stuck_jobs_by_status = AsyncMock(return_value=[])

    with (
        patch(f"{MODULE}.get_db_context", _fake_db),
        patch(f"{MODULE}.crud", mock_crud),
    ):
        await act.run()


@pytest.mark.unit
async def test_run_cancelling_pending_jobs(act, state_machine, workflow_service):
    stuck_job = _make_job(status="cancelling")

    mock_crud = MagicMock()
    mock_crud.sync_job.get_stuck_jobs_by_status = AsyncMock(
        side_effect=[
            [stuck_job],  # cancelling/pending query
            [],  # running query
        ]
    )
    mock_crud.organization.get = AsyncMock(return_value=_make_org())

    with (
        patch(f"{MODULE}.get_db_context", _fake_db),
        patch(f"{MODULE}.crud", mock_crud),
        patch(f"{MODULE}.asyncio.sleep", new_callable=AsyncMock),
    ):
        await act.run()

    assert len(state_machine.calls) == 1
    assert state_machine.calls[0]["target"] == SyncJobStatus.CANCELLED
    assert state_machine.calls[0]["error"] == _STUCK_CANCEL_REASON


@pytest.mark.unit
async def test_run_running_stuck_job_transitions_to_failed(act, state_machine):
    stuck_job = _make_job(status="running")

    mock_crud = MagicMock()
    mock_crud.sync_job.get_stuck_jobs_by_status = AsyncMock(
        side_effect=[
            [],  # cancelling/pending query
            [stuck_job],  # running query
        ]
    )
    mock_crud.entity.get_latest_entity_time_for_job = AsyncMock(return_value=None)
    mock_crud.organization.get = AsyncMock(return_value=_make_org())

    stale_snapshot = json.dumps({"inserted": 10})
    mock_redis_client = MagicMock()
    mock_redis_inner = AsyncMock()
    mock_redis_inner.get.return_value = stale_snapshot
    mock_redis_client.client = mock_redis_inner

    with (
        patch(f"{MODULE}.get_db_context", _fake_db),
        patch(f"{MODULE}.crud", mock_crud),
        patch(f"{MODULE}.redis_client", mock_redis_client),
        patch(f"{MODULE}.asyncio.sleep", new_callable=AsyncMock),
    ):
        await act.run()

    assert len(state_machine.calls) == 1
    assert state_machine.calls[0]["target"] == SyncJobStatus.FAILED
    assert state_machine.calls[0]["error"] == _STUCK_RUNNING_REASON


@pytest.mark.unit
async def test_run_handles_general_exception(act):
    mock_crud = MagicMock()
    mock_crud.sync_job.get_stuck_jobs_by_status = AsyncMock(
        side_effect=RuntimeError("db error")
    )

    with (
        patch(f"{MODULE}.get_db_context", _fake_db),
        patch(f"{MODULE}.crud", mock_crud),
        pytest.raises(RuntimeError, match="db error"),
    ):
        await act.run()


# ── _is_running_job_stuck() ──────────────────────────────────────────


@pytest.mark.unit
async def test_is_running_job_stuck_arf_only_skipped(act):
    job = _make_job(sync_config={"handlers": {"enable_postgres_handler": False}})
    cutoff = datetime(2025, 1, 1)
    result = await act._is_running_job_stuck(job, cutoff, AsyncMock(), MagicMock())
    assert result is False


@pytest.mark.unit
async def test_is_running_job_stuck_no_snapshot(act):
    job = _make_job()
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    with patch(f"{MODULE}.redis_client", _mock_redis(mock_redis)):
        result = await act._is_running_job_stuck(
            job, datetime(2025, 1, 1), AsyncMock(), MagicMock()
        )
    assert result is False


@pytest.mark.unit
async def test_is_running_job_stuck_no_timestamp_falls_back_to_db(act):
    job = _make_job()
    snapshot = json.dumps({"inserted": 10})
    mock_redis = AsyncMock()
    mock_redis.get.return_value = snapshot

    mock_crud = MagicMock()
    mock_crud.entity.get_latest_entity_time_for_job = AsyncMock(return_value=None)

    with (
        patch(f"{MODULE}.redis_client", _mock_redis(mock_redis)),
        patch(f"{MODULE}.crud", mock_crud),
    ):
        result = await act._is_running_job_stuck(
            job, datetime(2025, 1, 1), AsyncMock(), MagicMock()
        )
    assert result is True


@pytest.mark.unit
async def test_is_running_job_stuck_no_timestamp_entity_time_recent(act):
    job = _make_job()
    snapshot = json.dumps({"inserted": 10})
    mock_redis = AsyncMock()
    mock_redis.get.return_value = snapshot

    mock_crud = MagicMock()
    recent_time = datetime(2025, 6, 1)
    mock_crud.entity.get_latest_entity_time_for_job = AsyncMock(return_value=recent_time)

    with (
        patch(f"{MODULE}.redis_client", _mock_redis(mock_redis)),
        patch(f"{MODULE}.crud", mock_crud),
    ):
        result = await act._is_running_job_stuck(
            job, datetime(2025, 1, 1), AsyncMock(), MagicMock()
        )
    assert result is False


@pytest.mark.unit
async def test_is_running_job_stuck_old_timestamp(act):
    job = _make_job()
    old_time = datetime(2024, 1, 1).isoformat()
    snapshot = json.dumps({
        "last_update_timestamp": old_time,
        "inserted": 5,
        "updated": 3,
        "deleted": 0,
        "kept": 2,
        "skipped": 1,
    })
    mock_redis = AsyncMock()
    mock_redis.get.return_value = snapshot

    with patch(f"{MODULE}.redis_client", _mock_redis(mock_redis)):
        result = await act._is_running_job_stuck(
            job, datetime(2025, 1, 1), AsyncMock(), MagicMock()
        )
    assert result is True


@pytest.mark.unit
async def test_is_running_job_stuck_recent_timestamp_healthy(act):
    job = _make_job()
    recent_time = datetime(2025, 6, 1).isoformat()
    snapshot = json.dumps({"last_update_timestamp": recent_time})
    mock_redis = AsyncMock()
    mock_redis.get.return_value = snapshot

    with patch(f"{MODULE}.redis_client", _mock_redis(mock_redis)):
        result = await act._is_running_job_stuck(
            job, datetime(2025, 1, 1), AsyncMock(), MagicMock()
        )
    assert result is False


@pytest.mark.unit
async def test_is_running_job_stuck_timezone_aware_timestamp(act):
    job = _make_job()
    old_time = datetime(2024, 1, 1, tzinfo=None).isoformat() + "+00:00"
    snapshot = json.dumps({
        "last_update_timestamp": old_time,
        "inserted": 1,
    })
    mock_redis = AsyncMock()
    mock_redis.get.return_value = snapshot

    with patch(f"{MODULE}.redis_client", _mock_redis(mock_redis)):
        result = await act._is_running_job_stuck(
            job, datetime(2025, 1, 1), AsyncMock(), MagicMock()
        )
    assert result is True


@pytest.mark.unit
async def test_is_running_job_stuck_redis_exception_falls_back(act):
    job = _make_job()
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = RuntimeError("redis down")

    mock_crud = MagicMock()
    mock_crud.entity.get_latest_entity_time_for_job = AsyncMock(return_value=None)

    with (
        patch(f"{MODULE}.redis_client", _mock_redis(mock_redis)),
        patch(f"{MODULE}.crud", mock_crud),
    ):
        result = await act._is_running_job_stuck(
            job, datetime(2025, 1, 1), AsyncMock(), MagicMock()
        )
    assert result is True


# ── _cancel_stuck_job() ──────────────────────────────────────────────


@pytest.mark.unit
async def test_cancel_stuck_job_org_fetch_fails(act):
    job = _make_job()
    mock_crud = MagicMock()
    mock_crud.organization.get = AsyncMock(side_effect=RuntimeError("org not found"))

    with patch(f"{MODULE}.crud", mock_crud):
        result = await act._cancel_stuck_job(
            job, datetime(2025, 1, 1), AsyncMock(), MagicMock()
        )
    assert result is False


@pytest.mark.unit
async def test_cancel_stuck_job_cancel_raises(act, state_machine):
    job = _make_job(status="cancelling")
    act.temporal_workflow_service = FakeTemporalWorkflowService()

    mock_crud = MagicMock()
    mock_crud.organization.get = AsyncMock(return_value=_make_org())

    async def fail_transition(**kwargs):
        raise RuntimeError("transition failed")

    state_machine.transition = fail_transition

    with (
        patch(f"{MODULE}.crud", mock_crud),
        patch(f"{MODULE}.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await act._cancel_stuck_job(
            job, datetime(2025, 1, 1), AsyncMock(), MagicMock()
        )
    assert result is False


@pytest.mark.unit
async def test_cancel_stuck_job_running_job_success(act, state_machine, workflow_service):
    job = _make_job(status="running")

    mock_crud = MagicMock()
    mock_crud.organization.get = AsyncMock(return_value=_make_org())

    with (
        patch(f"{MODULE}.crud", mock_crud),
        patch(f"{MODULE}.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = await act._cancel_stuck_job(
            job, datetime(2025, 1, 1), AsyncMock(), MagicMock()
        )

    assert result is True
    assert state_machine.calls[0]["target"] == SyncJobStatus.FAILED


@pytest.mark.unit
async def test_cancel_stuck_job_cancel_returns_false(act, state_machine):
    job = _make_job(status="pending")
    act.temporal_workflow_service = FakeTemporalWorkflowService(cancel_result=False)

    mock_crud = MagicMock()
    mock_crud.organization.get = AsyncMock(return_value=_make_org())

    with patch(f"{MODULE}.crud", mock_crud):
        result = await act._cancel_stuck_job(
            job, datetime(2025, 1, 1), AsyncMock(), MagicMock()
        )

    assert result is True
    assert state_machine.calls[0]["target"] == SyncJobStatus.CANCELLED


@pytest.mark.unit
async def test_run_mixed_stuck_jobs_counts(act, state_machine):
    """Test run counts cancelled/failed jobs correctly."""
    cancelling_job = _make_job(
        job_id="00000000-0000-0000-0000-000000000021", status="cancelling"
    )
    running_job = _make_job(
        job_id="00000000-0000-0000-0000-000000000022", status="running"
    )

    mock_crud = MagicMock()
    mock_crud.sync_job.get_stuck_jobs_by_status = AsyncMock(
        side_effect=[
            [cancelling_job],  # cancelling/pending query
            [running_job],  # running query
        ]
    )
    mock_crud.entity.get_latest_entity_time_for_job = AsyncMock(return_value=None)
    mock_crud.organization.get = AsyncMock(return_value=_make_org())

    mock_redis = AsyncMock()
    mock_redis.get.return_value = json.dumps({"inserted": 10})

    with (
        patch(f"{MODULE}.get_db_context", _fake_db),
        patch(f"{MODULE}.crud", mock_crud),
        patch(f"{MODULE}.redis_client", _mock_redis(mock_redis)),
        patch(f"{MODULE}.asyncio.sleep", new_callable=AsyncMock),
    ):
        await act.run()

    assert len(state_machine.calls) == 2


@pytest.mark.unit
async def test_run_failed_count_incremented(act, state_machine):
    """When _cancel_stuck_job returns False, failed_count is incremented."""
    job = _make_job(status="cancelling")

    mock_crud = MagicMock()
    mock_crud.sync_job.get_stuck_jobs_by_status = AsyncMock(
        side_effect=[
            [job],  # cancelling/pending query
            [],  # running query
        ]
    )
    mock_crud.organization.get = AsyncMock(side_effect=RuntimeError("org not found"))

    with (
        patch(f"{MODULE}.get_db_context", _fake_db),
        patch(f"{MODULE}.crud", mock_crud),
        patch(f"{MODULE}.asyncio.sleep", new_callable=AsyncMock),
    ):
        await act.run()

    assert len(state_machine.calls) == 0
