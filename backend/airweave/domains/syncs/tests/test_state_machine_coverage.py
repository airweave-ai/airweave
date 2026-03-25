"""Coverage tests for SyncJobStateMachine — publish lifecycle edge cases."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from airweave.adapters.event_bus.fake import FakeEventBus
from airweave.core.shared_models import SyncJobStatus
from airweave.domains.syncs.fakes.sync_job_repository import FakeSyncJobRepository
from airweave.domains.syncs.state_machine import SyncJobStateMachine
from airweave.domains.syncs.types import LifecycleData

ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
SYNC_ID = UUID("00000000-0000-0000-0000-000000000010")
SYNC_JOB_ID = UUID("00000000-0000-0000-0000-000000000020")
COLLECTION_ID = UUID("00000000-0000-0000-0000-000000000030")
SC_ID = UUID("00000000-0000-0000-0000-000000000050")


def _make_lifecycle():
    return LifecycleData(
        organization_id=ORG_ID,
        sync_id=SYNC_ID,
        sync_job_id=SYNC_JOB_ID,
        collection_id=COLLECTION_ID,
        source_connection_id=SC_ID,
        source_type="test_source",
        collection_name="test",
        collection_readable_id="test",
    )


@pytest.mark.unit
async def test_publish_lifecycle_event_unknown_target():
    """CANCELLING has no lifecycle event factory → returns immediately."""
    sm = SyncJobStateMachine(
        sync_job_repo=MagicMock(),
        event_bus=FakeEventBus(),
    )

    await sm._publish_lifecycle_event(
        SyncJobStatus.CANCELLING, _make_lifecycle()
    )


@pytest.mark.unit
async def test_publish_lifecycle_event_publish_failure():
    """Publish failure logs a warning but doesn't raise."""

    class FailingEventBus:
        async def publish(self, event):
            raise RuntimeError("bus broken")

    sm = SyncJobStateMachine(
        sync_job_repo=MagicMock(),
        event_bus=FailingEventBus(),
    )

    await sm._publish_lifecycle_event(
        SyncJobStatus.COMPLETED, _make_lifecycle()
    )


@pytest.mark.unit
async def test_publish_lifecycle_event_failed_with_error():
    """FAILED target includes error kwarg when provided."""
    event_bus = FakeEventBus()
    sm = SyncJobStateMachine(
        sync_job_repo=MagicMock(),
        event_bus=event_bus,
    )

    await sm._publish_lifecycle_event(
        SyncJobStatus.FAILED, _make_lifecycle(), error="something broke"
    )

    assert len(event_bus.events) == 1
