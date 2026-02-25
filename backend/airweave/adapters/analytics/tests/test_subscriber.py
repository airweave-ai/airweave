"""Tests for AnalyticsEventSubscriber."""

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest

from airweave.adapters.analytics.fake import FakeAnalyticsTracker
from airweave.adapters.analytics.subscriber import AnalyticsEventSubscriber
from airweave.core.events.source_connection import SourceConnectionLifecycleEvent
from airweave.core.events.sync import SyncLifecycleEvent

ORG_ID = UUID("aaaaaaaa-0000-0000-0000-000000000001")
SC_ID = UUID("bbbbbbbb-0000-0000-0000-000000000001")
SYNC_ID = UUID("cccccccc-0000-0000-0000-000000000001")
JOB_ID = UUID("dddddddd-0000-0000-0000-000000000001")
COLL_ID = UUID("eeeeeeee-0000-0000-0000-000000000001")


def _build() -> tuple[FakeAnalyticsTracker, AnalyticsEventSubscriber]:
    tracker = FakeAnalyticsTracker()
    return tracker, AnalyticsEventSubscriber(tracker)


# ---------------------------------------------------------------------------
# Source connection events
# ---------------------------------------------------------------------------


@dataclass
class SCCase:
    id: str
    event: SourceConnectionLifecycleEvent
    expected_event_name: str
    expected_source_type: str = "slack"


SC_CASES = [
    SCCase(
        id="created",
        event=SourceConnectionLifecycleEvent.created(
            organization_id=ORG_ID,
            source_connection_id=SC_ID,
            source_type="slack",
            collection_readable_id="my-collection",
            is_authenticated=True,
        ),
        expected_event_name="source_connection_created",
    ),
    SCCase(
        id="auth_completed",
        event=SourceConnectionLifecycleEvent.auth_completed(
            organization_id=ORG_ID,
            source_connection_id=SC_ID,
            source_type="slack",
            collection_readable_id="my-collection",
        ),
        expected_event_name="source_connection_auth_completed",
    ),
    SCCase(
        id="deleted",
        event=SourceConnectionLifecycleEvent.deleted(
            organization_id=ORG_ID,
            source_connection_id=SC_ID,
            source_type="slack",
            collection_readable_id="my-collection",
        ),
        expected_event_name="source_connection_deleted",
    ),
]


@pytest.mark.parametrize("case", SC_CASES, ids=[c.id for c in SC_CASES])
@pytest.mark.asyncio
async def test_source_connection_events(case: SCCase):
    tracker, subscriber = _build()
    await subscriber.handle(case.event)

    tracked = tracker.get(case.expected_event_name)
    assert tracked.distinct_id == str(ORG_ID)
    assert tracked.properties["connection_id"] == str(SC_ID)
    assert tracked.properties["source_type"] == case.expected_source_type
    assert tracked.groups == {"organization": str(ORG_ID)}


@pytest.mark.asyncio
async def test_sc_created_includes_auth_fields():
    tracker, subscriber = _build()
    event = SourceConnectionLifecycleEvent.created(
        organization_id=ORG_ID,
        source_connection_id=SC_ID,
        source_type="notion",
        collection_readable_id="docs",
        is_authenticated=False,
    )
    await subscriber.handle(event)
    tracked = tracker.get("source_connection_created")
    assert tracked.properties["is_authenticated"] is False
    assert tracked.properties["collection_readable_id"] == "docs"


# ---------------------------------------------------------------------------
# Sync events
# ---------------------------------------------------------------------------


@dataclass
class SyncCase:
    id: str
    event: SyncLifecycleEvent
    expected_event_name: str


SYNC_CASES = [
    SyncCase(
        id="completed",
        event=SyncLifecycleEvent.completed(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=JOB_ID,
            collection_id=COLL_ID,
            source_connection_id=SC_ID,
            source_type="github",
            collection_name="Code",
            collection_readable_id="code",
            entities_inserted=10,
            entities_updated=5,
            entities_deleted=2,
            entities_skipped=1,
            chunks_written=42,
        ),
        expected_event_name="sync_completed",
    ),
    SyncCase(
        id="failed",
        event=SyncLifecycleEvent.failed(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=JOB_ID,
            collection_id=COLL_ID,
            source_connection_id=SC_ID,
            source_type="github",
            collection_name="Code",
            collection_readable_id="code",
            error="connection timeout",
        ),
        expected_event_name="sync_failed",
    ),
    SyncCase(
        id="cancelled",
        event=SyncLifecycleEvent.cancelled(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=JOB_ID,
            collection_id=COLL_ID,
            source_connection_id=SC_ID,
            source_type="github",
            collection_name="Code",
            collection_readable_id="code",
        ),
        expected_event_name="sync_cancelled",
    ),
]


@pytest.mark.parametrize("case", SYNC_CASES, ids=[c.id for c in SYNC_CASES])
@pytest.mark.asyncio
async def test_sync_events(case: SyncCase):
    tracker, subscriber = _build()
    await subscriber.handle(case.event)

    tracked = tracker.get(case.expected_event_name)
    assert tracked.distinct_id == str(ORG_ID)
    assert tracked.properties["sync_id"] == str(SYNC_ID)
    assert tracked.groups == {"organization": str(ORG_ID)}


@pytest.mark.asyncio
async def test_sync_completed_metrics():
    tracker, subscriber = _build()
    event = SyncLifecycleEvent.completed(
        organization_id=ORG_ID,
        sync_id=SYNC_ID,
        sync_job_id=JOB_ID,
        collection_id=COLL_ID,
        source_connection_id=SC_ID,
        source_type="notion",
        collection_name="Docs",
        collection_readable_id="docs",
        entities_inserted=100,
        entities_updated=50,
        entities_deleted=10,
        entities_skipped=5,
        chunks_written=200,
    )
    await subscriber.handle(event)

    tracked = tracker.get("sync_completed")
    assert tracked.properties["entities_inserted"] == 100
    assert tracked.properties["entities_updated"] == 50
    assert tracked.properties["entities_synced"] == 150
    assert tracked.properties["chunks_written"] == 200


@pytest.mark.asyncio
async def test_sync_failed_error():
    tracker, subscriber = _build()
    event = SyncLifecycleEvent.failed(
        organization_id=ORG_ID,
        sync_id=SYNC_ID,
        sync_job_id=JOB_ID,
        collection_id=COLL_ID,
        source_connection_id=SC_ID,
        source_type="slack",
        collection_name="Chat",
        collection_readable_id="chat",
        error="rate limit exceeded",
    )
    await subscriber.handle(event)
    tracked = tracker.get("sync_failed")
    assert tracked.properties["error"] == "rate limit exceeded"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unhandled_event_type_is_ignored():
    """Events without a registered handler are silently skipped."""
    tracker, subscriber = _build()
    event = SyncLifecycleEvent.pending(
        organization_id=ORG_ID,
        sync_id=SYNC_ID,
        sync_job_id=JOB_ID,
        collection_id=COLL_ID,
        source_connection_id=SC_ID,
        source_type="slack",
        collection_name="Chat",
        collection_readable_id="chat",
    )
    await subscriber.handle(event)
    assert len(tracker.events) == 0


@pytest.mark.asyncio
async def test_multiple_events_tracked_independently():
    tracker, subscriber = _build()

    await subscriber.handle(
        SourceConnectionLifecycleEvent.created(
            organization_id=ORG_ID,
            source_connection_id=SC_ID,
            source_type="slack",
            collection_readable_id="col",
        )
    )
    await subscriber.handle(
        SourceConnectionLifecycleEvent.deleted(
            organization_id=ORG_ID,
            source_connection_id=SC_ID,
            source_type="slack",
            collection_readable_id="col",
        )
    )

    assert len(tracker.events) == 2
    assert tracker.events[0].event_name == "source_connection_created"
    assert tracker.events[1].event_name == "source_connection_deleted"
