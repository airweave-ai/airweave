"""Unit tests for SyncProgressRelay — session lifecycle, accumulation, and publishing."""

import json
from uuid import UUID, uuid4

import pytest

from airweave.adapters.pubsub.fake import FakePubSub
from airweave.core.events.enums import SyncEventType
from airweave.core.events.sync import (
    AccessControlMembershipBatchProcessedEvent,
    EntityBatchProcessedEvent,
    SyncLifecycleEvent,
    TypeActionCounts,
)
from airweave.core.shared_models import SyncJobStatus
from airweave.platform.sync.subscribers.progress_relay import SyncProgressRelay

ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
SYNC_ID = uuid4()
JOB_ID = uuid4()
COLLECTION_ID = uuid4()
SC_ID = uuid4()


def _make_relay():
    pubsub = FakePubSub()
    relay = SyncProgressRelay(pubsub=pubsub)
    return relay, pubsub


def _running_event(
    sync_id=SYNC_ID, job_id=JOB_ID
) -> SyncLifecycleEvent:
    return SyncLifecycleEvent.running(
        organization_id=ORG_ID,
        sync_id=sync_id,
        sync_job_id=job_id,
        collection_id=COLLECTION_ID,
        source_connection_id=SC_ID,
        source_type="stub",
        collection_name="test",
        collection_readable_id="test-col",
    )


def _batch_event(
    inserted=5, updated=3, deleted=1, kept=2,
    job_id=JOB_ID, billable=True, type_breakdown=None,
) -> EntityBatchProcessedEvent:
    return EntityBatchProcessedEvent(
        organization_id=ORG_ID,
        sync_id=SYNC_ID,
        sync_job_id=job_id,
        collection_id=COLLECTION_ID,
        source_connection_id=SC_ID,
        inserted=inserted,
        updated=updated,
        deleted=deleted,
        kept=kept,
        billable=billable,
        type_breakdown=type_breakdown or {},
    )


def _completed_event(job_id=JOB_ID) -> SyncLifecycleEvent:
    return SyncLifecycleEvent.completed(
        organization_id=ORG_ID,
        sync_id=SYNC_ID,
        sync_job_id=job_id,
        collection_id=COLLECTION_ID,
        source_connection_id=SC_ID,
        source_type="stub",
        collection_name="test",
        collection_readable_id="test-col",
    )


def _failed_event(job_id=JOB_ID) -> SyncLifecycleEvent:
    return SyncLifecycleEvent.failed(
        organization_id=ORG_ID,
        sync_id=SYNC_ID,
        sync_job_id=job_id,
        collection_id=COLLECTION_ID,
        source_connection_id=SC_ID,
        source_type="stub",
        collection_name="test",
        collection_readable_id="test-col",
        error="boom",
    )


# ---------------------------------------------------------------------------
# Session auto-creation on sync.running
# ---------------------------------------------------------------------------


class TestSessionCreation:
    @pytest.mark.asyncio
    async def test_running_creates_session(self):
        relay, _ = _make_relay()

        await relay.handle(_running_event())

        assert relay.active_session_count == 1

    @pytest.mark.asyncio
    async def test_multiple_syncs_create_separate_sessions(self):
        relay, _ = _make_relay()
        job_a, job_b = uuid4(), uuid4()

        await relay.handle(_running_event(job_id=job_a))
        await relay.handle(_running_event(job_id=job_b))

        assert relay.active_session_count == 2

    @pytest.mark.asyncio
    async def test_batch_without_session_is_ignored(self):
        relay, pubsub = _make_relay()

        await relay.handle(_batch_event(job_id=uuid4()))

        assert len(pubsub.published) == 0


# ---------------------------------------------------------------------------
# Batch accumulation in _RelaySession
# ---------------------------------------------------------------------------


class TestBatchAccumulation:
    @pytest.mark.asyncio
    async def test_accumulates_entity_counts(self):
        relay, _ = _make_relay()
        await relay.handle(_running_event())

        await relay.handle(_batch_event(inserted=10, updated=5, deleted=2, kept=3))

        session = relay._sessions[JOB_ID]
        assert session.inserted == 10
        assert session.updated == 5
        assert session.deleted == 2
        assert session.kept == 3
        assert session.total_entities == 15  # inserted + updated

    @pytest.mark.asyncio
    async def test_accumulates_across_batches(self):
        relay, _ = _make_relay()
        await relay.handle(_running_event())

        await relay.handle(_batch_event(inserted=10, updated=5, deleted=0, kept=0))
        await relay.handle(_batch_event(inserted=3, updated=2, deleted=1, kept=4))

        session = relay._sessions[JOB_ID]
        assert session.inserted == 13
        assert session.updated == 7
        assert session.deleted == 1
        assert session.kept == 4

    @pytest.mark.asyncio
    async def test_accumulates_type_breakdown(self):
        relay, _ = _make_relay()
        await relay.handle(_running_event())

        breakdown = {
            "FileEntity": TypeActionCounts(inserted=5, updated=2, deleted=0, kept=1),
            "FolderEntity": TypeActionCounts(inserted=3, updated=0, deleted=0, kept=0),
        }
        await relay.handle(_batch_event(
            inserted=8, updated=2, deleted=0, kept=1,
            type_breakdown=breakdown,
        ))

        session = relay._sessions[JOB_ID]
        assert "FileEntity" in session.type_counts
        assert session.type_counts["FileEntity"].inserted == 5
        assert session.type_counts["FolderEntity"].inserted == 3

    @pytest.mark.asyncio
    async def test_type_breakdown_merges_across_batches(self):
        relay, _ = _make_relay()
        await relay.handle(_running_event())

        batch1 = {"FileEntity": TypeActionCounts(inserted=3, updated=1, deleted=0, kept=0)}
        batch2 = {"FileEntity": TypeActionCounts(inserted=2, updated=4, deleted=0, kept=0)}

        await relay.handle(_batch_event(inserted=3, updated=1, deleted=0, kept=0, type_breakdown=batch1))
        await relay.handle(_batch_event(inserted=2, updated=4, deleted=0, kept=0, type_breakdown=batch2))

        session = relay._sessions[JOB_ID]
        assert session.type_counts["FileEntity"].inserted == 5
        assert session.type_counts["FileEntity"].updated == 5


# ---------------------------------------------------------------------------
# Throttled publishing
# ---------------------------------------------------------------------------


class TestThrottledPublishing:
    @pytest.mark.asyncio
    async def test_publishes_after_threshold(self):
        """Default publish_threshold is 3 ops; a batch with >=3 ops triggers publish."""
        relay, pubsub = _make_relay()
        await relay.handle(_running_event())

        # 5+3+1+2 = 11 ops, well above threshold of 3
        await relay.handle(_batch_event(inserted=5, updated=3, deleted=1, kept=2))

        progress_msgs = pubsub.published.get(("sync_job", str(JOB_ID)), [])
        assert len(progress_msgs) >= 1

    @pytest.mark.asyncio
    async def test_does_not_publish_below_threshold(self):
        """A tiny batch that doesn't cross the threshold should not publish."""
        relay, pubsub = _make_relay()
        await relay.handle(_running_event())

        # 1+0+0+0 = 1 op, below threshold of 3
        await relay.handle(_batch_event(inserted=1, updated=0, deleted=0, kept=0))

        progress_msgs = pubsub.published.get(("sync_job", str(JOB_ID)), [])
        assert len(progress_msgs) == 0

    @pytest.mark.asyncio
    async def test_stores_snapshot_on_publish(self):
        relay, pubsub = _make_relay()
        await relay.handle(_running_event())

        await relay.handle(_batch_event(inserted=5, updated=3, deleted=1, kept=2))

        snapshot_key = f"sync_progress_snapshot:{JOB_ID}"
        assert snapshot_key in pubsub.snapshots
        data_str, ttl = pubsub.snapshots[snapshot_key]
        assert ttl == 1800
        snapshot = json.loads(data_str)
        assert snapshot["inserted"] == 5

    @pytest.mark.asyncio
    async def test_publishes_entity_state_on_publish(self):
        relay, pubsub = _make_relay()
        await relay.handle(_running_event())

        await relay.handle(_batch_event(inserted=5, updated=3, deleted=1, kept=2))

        state_msgs = pubsub.published.get(("sync_job_state", str(JOB_ID)), [])
        assert len(state_msgs) >= 1


# ---------------------------------------------------------------------------
# ACL membership batch
# ---------------------------------------------------------------------------


class TestAclBatch:
    @pytest.mark.asyncio
    async def test_acl_batch_triggers_progress_publish(self):
        relay, pubsub = _make_relay()
        await relay.handle(_running_event())

        acl_event = AccessControlMembershipBatchProcessedEvent(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=JOB_ID,
            source_connection_id=SC_ID,
            collected=50,
            upserted=50,
        )
        await relay.handle(acl_event)

        progress_msgs = pubsub.published.get(("sync_job", str(JOB_ID)), [])
        assert len(progress_msgs) >= 1

    @pytest.mark.asyncio
    async def test_acl_batch_without_session_is_ignored(self):
        relay, pubsub = _make_relay()

        acl_event = AccessControlMembershipBatchProcessedEvent(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=uuid4(),
            source_connection_id=SC_ID,
            collected=10,
            upserted=10,
        )
        await relay.handle(acl_event)

        assert len(pubsub.published) == 0


# ---------------------------------------------------------------------------
# Terminal events (completed / failed / cancelled)
# ---------------------------------------------------------------------------


class TestTerminalEvents:
    @pytest.mark.asyncio
    async def test_completed_publishes_final_state(self):
        relay, pubsub = _make_relay()
        await relay.handle(_running_event())
        await relay.handle(_batch_event(inserted=10, updated=5, deleted=0, kept=0))

        await relay.handle(_completed_event())

        progress_msgs = pubsub.published[("sync_job", str(JOB_ID))]
        final = progress_msgs[-1]
        assert final["status"] == SyncJobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_completed_publishes_completion_message(self):
        relay, pubsub = _make_relay()
        await relay.handle(_running_event())
        await relay.handle(_batch_event(inserted=10, updated=5, deleted=0, kept=0))

        await relay.handle(_completed_event())

        state_msgs = pubsub.published[("sync_job_state", str(JOB_ID))]
        final_raw = state_msgs[-1]
        final = json.loads(final_raw) if isinstance(final_raw, str) else final_raw
        assert final["is_complete"] is True
        assert final["is_failed"] is False
        assert final["total_entities"] == 15

    @pytest.mark.asyncio
    async def test_failed_publishes_error(self):
        relay, pubsub = _make_relay()
        await relay.handle(_running_event())

        await relay.handle(_failed_event())

        progress_msgs = pubsub.published[("sync_job", str(JOB_ID))]
        final = progress_msgs[-1]
        assert final["status"] == SyncJobStatus.FAILED

        state_msgs = pubsub.published[("sync_job_state", str(JOB_ID))]
        final_raw = state_msgs[-1]
        final_state = json.loads(final_raw) if isinstance(final_raw, str) else final_raw
        assert final_state["is_failed"] is True
        assert final_state["error"] == "boom"

    @pytest.mark.asyncio
    async def test_cancelled_marks_session_finished(self):
        relay, _ = _make_relay()
        await relay.handle(_running_event())

        cancelled = SyncLifecycleEvent.cancelled(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID,
            source_connection_id=SC_ID,
            source_type="stub",
            collection_name="test",
            collection_readable_id="test-col",
        )
        await relay.handle(cancelled)

        assert relay._sessions[JOB_ID].is_finished
        assert relay.active_session_count == 0

    @pytest.mark.asyncio
    async def test_terminal_without_session_is_noop(self):
        relay, pubsub = _make_relay()

        await relay.handle(_completed_event(job_id=uuid4()))

        assert len(pubsub.published) == 0

    @pytest.mark.asyncio
    async def test_batch_after_terminal_is_ignored(self):
        relay, pubsub = _make_relay()
        await relay.handle(_running_event())
        await relay.handle(_completed_event())

        pubsub.clear()
        await relay.handle(_batch_event(inserted=100, updated=0, deleted=0, kept=0))

        assert len(pubsub.published) == 0


# ---------------------------------------------------------------------------
# Pending event does not create session
# ---------------------------------------------------------------------------


class TestPendingEvent:
    @pytest.mark.asyncio
    async def test_pending_does_not_create_session(self):
        relay, _ = _make_relay()

        pending = SyncLifecycleEvent.pending(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID,
            source_connection_id=SC_ID,
            source_type="stub",
            collection_name="test",
            collection_readable_id="test-col",
        )
        await relay.handle(pending)

        assert relay.active_session_count == 0


# ---------------------------------------------------------------------------
# named_counts helper
# ---------------------------------------------------------------------------


class TestNamedCounts:
    @pytest.mark.asyncio
    async def test_named_counts_sums_inserted_updated_kept(self):
        relay, _ = _make_relay()
        await relay.handle(_running_event())

        breakdown = {
            "FileEntity": TypeActionCounts(inserted=5, updated=2, deleted=3, kept=10),
        }
        await relay.handle(_batch_event(
            inserted=5, updated=2, deleted=3, kept=10,
            type_breakdown=breakdown,
        ))

        session = relay._sessions[JOB_ID]
        assert session.named_counts["FileEntity"] == 17  # 5 + 2 + 10
