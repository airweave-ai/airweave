"""Tests for SyncJobStateMachine — transition validation, DB updates, lifecycle events."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from airweave.core.shared_models import SyncJobStatus
from airweave.domains.sync_pipeline.pipeline.entity_tracker import SyncStats
from airweave.domains.syncs.state_machine import SyncJobStateMachine
from airweave.domains.syncs.types import InvalidTransitionError, LifecycleData

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ORG_ID = uuid4()
SYNC_ID = uuid4()
JOB_ID = uuid4()
COLLECTION_ID = uuid4()
SC_ID = uuid4()


def _make_lifecycle_data() -> LifecycleData:
    return LifecycleData(
        organization_id=ORG_ID,
        sync_id=SYNC_ID,
        sync_job_id=JOB_ID,
        collection_id=COLLECTION_ID,
        source_connection_id=SC_ID,
        source_type="test_source",
        collection_name="test-collection",
        collection_readable_id="test-collection",
    )


def _make_db_job(status: SyncJobStatus, job_id: UUID = JOB_ID) -> MagicMock:
    job = MagicMock()
    job.id = job_id
    job.status = status.value
    return job


def _make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.organization = MagicMock()
    ctx.organization.id = ORG_ID
    return ctx


# ---------------------------------------------------------------------------
# Pure validation tests
# ---------------------------------------------------------------------------


@dataclass
class TransitionCase:
    name: str
    current: SyncJobStatus
    target: SyncJobStatus
    should_raise: bool


VALID_TRANSITIONS = [
    TransitionCase("pending_to_running", SyncJobStatus.PENDING, SyncJobStatus.RUNNING, False),
    TransitionCase("pending_to_cancelled", SyncJobStatus.PENDING, SyncJobStatus.CANCELLED, False),
    TransitionCase("pending_to_failed", SyncJobStatus.PENDING, SyncJobStatus.FAILED, False),
    TransitionCase("running_to_completed", SyncJobStatus.RUNNING, SyncJobStatus.COMPLETED, False),
    TransitionCase("running_to_failed", SyncJobStatus.RUNNING, SyncJobStatus.FAILED, False),
    TransitionCase(
        "running_to_cancelling", SyncJobStatus.RUNNING, SyncJobStatus.CANCELLING, False
    ),
    TransitionCase(
        "cancelling_to_cancelled", SyncJobStatus.CANCELLING, SyncJobStatus.CANCELLED, False
    ),
    TransitionCase("idempotent_same", SyncJobStatus.RUNNING, SyncJobStatus.RUNNING, False),
]

INVALID_TRANSITIONS = [
    TransitionCase(
        "completed_to_running", SyncJobStatus.COMPLETED, SyncJobStatus.RUNNING, True
    ),
    TransitionCase("failed_to_running", SyncJobStatus.FAILED, SyncJobStatus.RUNNING, True),
    TransitionCase(
        "cancelled_to_running", SyncJobStatus.CANCELLED, SyncJobStatus.RUNNING, True
    ),
    TransitionCase(
        "pending_to_completed", SyncJobStatus.PENDING, SyncJobStatus.COMPLETED, True
    ),
    TransitionCase(
        "cancelling_to_running", SyncJobStatus.CANCELLING, SyncJobStatus.RUNNING, True
    ),
    TransitionCase(
        "cancelling_to_completed", SyncJobStatus.CANCELLING, SyncJobStatus.COMPLETED, True
    ),
]


@pytest.mark.parametrize(
    "case", VALID_TRANSITIONS + INVALID_TRANSITIONS, ids=lambda c: c.name
)
def test_validate_transition(case: TransitionCase) -> None:
    if case.should_raise:
        with pytest.raises(InvalidTransitionError):
            SyncJobStateMachine._validate_transition(case.current, case.target)
    else:
        SyncJobStateMachine._validate_transition(case.current, case.target)


# ---------------------------------------------------------------------------
# State machine integration tests (with mocked DB)
# ---------------------------------------------------------------------------


@pytest.fixture
def sm() -> tuple[SyncJobStateMachine, MagicMock, AsyncMock]:
    repo = MagicMock()
    repo.get = AsyncMock()
    repo.update = AsyncMock()
    event_bus = AsyncMock()
    event_bus.publish = AsyncMock()
    machine = SyncJobStateMachine(sync_job_repo=repo, event_bus=event_bus)
    return machine, repo, event_bus


@pytest.mark.asyncio
@patch("airweave.domains.syncs.state_machine.get_db_context")
async def test_transition_happy_path(mock_db_ctx, sm):
    machine, repo, event_bus = sm
    db = AsyncMock()
    db.commit = AsyncMock()
    mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

    db_job = _make_db_job(SyncJobStatus.PENDING)
    repo.get.return_value = db_job

    ctx = _make_ctx()
    result = await machine.transition(
        sync_job_id=JOB_ID,
        target=SyncJobStatus.RUNNING,
        ctx=ctx,
        lifecycle_data=_make_lifecycle_data(),
    )

    assert result.applied is True
    assert result.previous == SyncJobStatus.PENDING
    assert result.current == SyncJobStatus.RUNNING
    repo.update.assert_called_once()
    event_bus.publish.assert_called_once()


@pytest.mark.asyncio
@patch("airweave.domains.syncs.state_machine.get_db_context")
async def test_transition_idempotent(mock_db_ctx, sm):
    machine, repo, event_bus = sm
    db = AsyncMock()
    mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

    db_job = _make_db_job(SyncJobStatus.RUNNING)
    repo.get.return_value = db_job

    ctx = _make_ctx()
    result = await machine.transition(
        sync_job_id=JOB_ID,
        target=SyncJobStatus.RUNNING,
        ctx=ctx,
    )

    assert result.applied is False
    assert result.previous == SyncJobStatus.RUNNING
    assert result.current == SyncJobStatus.RUNNING
    repo.update.assert_not_called()
    event_bus.publish.assert_not_called()


@pytest.mark.asyncio
@patch("airweave.domains.syncs.state_machine.get_db_context")
async def test_transition_invalid_raises(mock_db_ctx, sm):
    machine, repo, event_bus = sm
    db = AsyncMock()
    mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

    db_job = _make_db_job(SyncJobStatus.COMPLETED)
    repo.get.return_value = db_job

    ctx = _make_ctx()
    with pytest.raises(InvalidTransitionError):
        await machine.transition(
            sync_job_id=JOB_ID,
            target=SyncJobStatus.RUNNING,
            ctx=ctx,
        )


@pytest.mark.asyncio
@patch("airweave.domains.syncs.state_machine.get_db_context")
async def test_transition_not_found_raises(mock_db_ctx, sm):
    machine, repo, event_bus = sm
    db = AsyncMock()
    mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

    repo.get.return_value = None

    ctx = _make_ctx()
    with pytest.raises(ValueError, match="not found"):
        await machine.transition(
            sync_job_id=JOB_ID,
            target=SyncJobStatus.RUNNING,
            ctx=ctx,
        )

    repo.update.assert_not_called()


@pytest.mark.asyncio
@patch("airweave.domains.syncs.state_machine.get_db_context")
async def test_transition_no_event_without_lifecycle_data(mock_db_ctx, sm):
    machine, repo, event_bus = sm
    db = AsyncMock()
    db.commit = AsyncMock()
    mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

    db_job = _make_db_job(SyncJobStatus.RUNNING)
    repo.get.return_value = db_job

    ctx = _make_ctx()
    result = await machine.transition(
        sync_job_id=JOB_ID,
        target=SyncJobStatus.COMPLETED,
        ctx=ctx,
    )

    assert result.applied is True
    event_bus.publish.assert_not_called()


@pytest.mark.asyncio
@patch("airweave.domains.syncs.state_machine.get_db_context")
async def test_transition_failed_includes_error(mock_db_ctx, sm):
    machine, repo, event_bus = sm
    db = AsyncMock()
    db.commit = AsyncMock()
    mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

    db_job = _make_db_job(SyncJobStatus.RUNNING)
    repo.get.return_value = db_job

    ctx = _make_ctx()
    result = await machine.transition(
        sync_job_id=JOB_ID,
        target=SyncJobStatus.FAILED,
        ctx=ctx,
        error="something broke",
        lifecycle_data=_make_lifecycle_data(),
    )

    assert result.applied is True
    assert result.current == SyncJobStatus.FAILED

    update_call = repo.update.call_args
    update_obj = update_call[1]["obj_in"] if "obj_in" in update_call[1] else update_call[0][2]
    assert update_obj.status == SyncJobStatus.FAILED
    assert update_obj.error == "something broke"
    assert update_obj.failed_at is not None


# ---------------------------------------------------------------------------
# _build_update tests
# ---------------------------------------------------------------------------


class TestBuildUpdate:
    def test_running_sets_started_at(self):
        update = SyncJobStateMachine._build_update(SyncJobStatus.RUNNING)
        assert update.status == SyncJobStatus.RUNNING
        assert update.started_at is not None
        assert update.completed_at is None
        assert update.failed_at is None

    def test_completed_sets_completed_at(self):
        update = SyncJobStateMachine._build_update(SyncJobStatus.COMPLETED)
        assert update.completed_at is not None
        assert update.failed_at is None

    def test_failed_sets_failed_at(self):
        update = SyncJobStateMachine._build_update(SyncJobStatus.FAILED, error="oops")
        assert update.failed_at is not None
        assert update.error == "oops"

    def test_cancelled_sets_completed_at(self):
        update = SyncJobStateMachine._build_update(SyncJobStatus.CANCELLED)
        assert update.completed_at is not None
        assert update.failed_at is None

    def test_cancelling_sets_no_timestamp(self):
        update = SyncJobStateMachine._build_update(SyncJobStatus.CANCELLING)
        assert update.started_at is None
        assert update.completed_at is None
        assert update.failed_at is None

    def test_stats_are_included(self):
        stats = SyncStats(inserted=10, updated=5, deleted=2, kept=3, skipped=1)
        update = SyncJobStateMachine._build_update(SyncJobStatus.COMPLETED, stats=stats)
        assert update.entities_inserted == 10
        assert update.entities_updated == 5
        assert update.entities_deleted == 2
        assert update.entities_kept == 3
        assert update.entities_skipped == 1
