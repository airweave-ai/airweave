"""Tests for TransitionSyncJobActivity."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from airweave.core.shared_models import SyncJobStatus
from airweave.domains.temporal.activities.transition_sync_job import (
    TransitionSyncJobActivity,
    _STATUS_MAP,
)

from .conftest import ORG_ID, SYNC_ID, SYNC_JOB_ID, make_ctx_dict


class FakeStateMachine:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def transition(self, **kwargs):
        self.calls.append(kwargs)
        return MagicMock(applied=True)


@pytest.fixture
def state_machine():
    return FakeStateMachine()


@pytest.fixture
def activity(state_machine):
    return TransitionSyncJobActivity(state_machine=state_machine)


@pytest.mark.unit
async def test_unknown_transition_raises(activity):
    with pytest.raises(ValueError, match="Unknown transition"):
        await activity.run(
            transition="explode",
            sync_job_id=SYNC_JOB_ID,
            ctx_dict=make_ctx_dict(),
            lifecycle_data={
                "organization_id": ORG_ID,
                "sync_id": SYNC_ID,
                "sync_job_id": SYNC_JOB_ID,
                "collection_id": "00000000-0000-0000-0000-000000000030",
                "source_connection_id": "00000000-0000-0000-0000-000000000050",
            },
        )


@pytest.mark.unit
async def test_completed_transition(activity, state_machine):
    lifecycle = {
        "organization_id": ORG_ID,
        "sync_id": SYNC_ID,
        "sync_job_id": SYNC_JOB_ID,
        "collection_id": "00000000-0000-0000-0000-000000000030",
        "source_connection_id": "00000000-0000-0000-0000-000000000050",
        "source_type": "test_source",
        "collection_name": "test-collection",
        "collection_readable_id": "test-collection",
    }

    await activity.run(
        transition="completed",
        sync_job_id=SYNC_JOB_ID,
        ctx_dict=make_ctx_dict(),
        lifecycle_data=lifecycle,
    )

    assert len(state_machine.calls) == 1
    call = state_machine.calls[0]
    assert call["sync_job_id"] == UUID(SYNC_JOB_ID)
    assert call["target"] == SyncJobStatus.COMPLETED
    assert isinstance(call["lifecycle_data"].organization_id, UUID)


@pytest.mark.unit
async def test_failed_transition_with_error(activity, state_machine):
    lifecycle = {
        "organization_id": ORG_ID,
        "sync_id": SYNC_ID,
        "sync_job_id": SYNC_JOB_ID,
        "collection_id": "00000000-0000-0000-0000-000000000030",
        "source_connection_id": "00000000-0000-0000-0000-000000000050",
    }

    await activity.run(
        transition="failed",
        sync_job_id=SYNC_JOB_ID,
        ctx_dict=make_ctx_dict(),
        lifecycle_data=lifecycle,
        error="Something went wrong",
    )

    call = state_machine.calls[0]
    assert call["target"] == SyncJobStatus.FAILED
    assert call["error"] == "Something went wrong"


@pytest.mark.unit
async def test_cancelled_transition(activity, state_machine):
    lifecycle = {
        "organization_id": ORG_ID,
        "sync_id": SYNC_ID,
        "sync_job_id": SYNC_JOB_ID,
        "collection_id": "00000000-0000-0000-0000-000000000030",
        "source_connection_id": "00000000-0000-0000-0000-000000000050",
    }

    await activity.run(
        transition="cancelled",
        sync_job_id=SYNC_JOB_ID,
        ctx_dict=make_ctx_dict(),
        lifecycle_data=lifecycle,
        error="User cancelled",
    )

    call = state_machine.calls[0]
    assert call["target"] == SyncJobStatus.CANCELLED


@pytest.mark.unit
async def test_transition_with_stats(activity, state_machine):
    lifecycle = {
        "organization_id": ORG_ID,
        "sync_id": SYNC_ID,
        "sync_job_id": SYNC_JOB_ID,
        "collection_id": "00000000-0000-0000-0000-000000000030",
        "source_connection_id": "00000000-0000-0000-0000-000000000050",
    }
    stats = {"inserted": 10, "updated": 5, "deleted": 0, "kept": 3, "skipped": 1}

    await activity.run(
        transition="completed",
        sync_job_id=SYNC_JOB_ID,
        ctx_dict=make_ctx_dict(),
        lifecycle_data=lifecycle,
        stats_dict=stats,
    )

    call = state_machine.calls[0]
    assert call["stats"].inserted == 10
    assert call["stats"].updated == 5


@pytest.mark.unit
async def test_transition_with_non_uuid_lifecycle_fields(activity, state_machine):
    """Non-UUID fields in lifecycle_data should pass through without conversion."""
    lifecycle = {
        "organization_id": ORG_ID,
        "sync_id": SYNC_ID,
        "sync_job_id": SYNC_JOB_ID,
        "collection_id": "00000000-0000-0000-0000-000000000030",
        "source_connection_id": "00000000-0000-0000-0000-000000000050",
        "source_type": "slack",
        "collection_name": "my collection",
        "collection_readable_id": "my-collection",
    }

    await activity.run(
        transition="completed",
        sync_job_id=SYNC_JOB_ID,
        ctx_dict=make_ctx_dict(),
        lifecycle_data=lifecycle,
    )

    ld = state_machine.calls[0]["lifecycle_data"]
    assert ld.source_type == "slack"
    assert ld.collection_name == "my collection"
