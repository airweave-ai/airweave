"""Unit tests for UsageBillingListener — event routing to the usage ledger."""

from uuid import UUID, uuid4

import pytest

from airweave.core.events.enums import SourceConnectionEventType, SyncEventType
from airweave.core.events.source_connection import SourceConnectionLifecycleEvent
from airweave.core.events.sync import (
    EntityBatchProcessedEvent,
    QueryProcessedEvent,
    SyncLifecycleEvent,
)
from airweave.domains.usage.fakes.ledger import FakeUsageLedger
from airweave.domains.usage.subscribers.billing_listener import UsageBillingListener
from airweave.domains.usage.types import ActionType

ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
SYNC_ID = uuid4()
JOB_ID = uuid4()
COLLECTION_ID = uuid4()
SC_ID = uuid4()


def _make_listener():
    ledger = FakeUsageLedger()
    listener = UsageBillingListener(ledger=ledger)
    return listener, ledger


# ---------------------------------------------------------------------------
# EntityBatchProcessedEvent
# ---------------------------------------------------------------------------


class TestEntityBatchRouting:
    @pytest.mark.asyncio
    async def test_records_inserted_plus_updated(self):
        listener, ledger = _make_listener()
        event = EntityBatchProcessedEvent(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID,
            source_connection_id=SC_ID,
            inserted=10,
            updated=5,
            deleted=2,
            kept=3,
            billable=True,
        )

        await listener.handle(event)

        assert ledger.recorded[(ORG_ID, ActionType.ENTITIES)] == 15

    @pytest.mark.asyncio
    async def test_skips_non_billable(self):
        listener, ledger = _make_listener()
        event = EntityBatchProcessedEvent(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID,
            source_connection_id=SC_ID,
            inserted=50,
            updated=25,
            billable=False,
        )

        await listener.handle(event)

        assert (ORG_ID, ActionType.ENTITIES) not in ledger.recorded

    @pytest.mark.asyncio
    async def test_skips_zero_entities(self):
        listener, ledger = _make_listener()
        event = EntityBatchProcessedEvent(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID,
            source_connection_id=SC_ID,
            inserted=0,
            updated=0,
            billable=True,
        )

        await listener.handle(event)

        assert len(ledger.record_calls) == 0

    @pytest.mark.asyncio
    async def test_only_counts_inserted_and_updated(self):
        """Deleted and kept entities should not be billed."""
        listener, ledger = _make_listener()
        event = EntityBatchProcessedEvent(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID,
            source_connection_id=SC_ID,
            inserted=7,
            updated=3,
            deleted=100,
            kept=200,
            billable=True,
        )

        await listener.handle(event)

        assert ledger.recorded[(ORG_ID, ActionType.ENTITIES)] == 10


# ---------------------------------------------------------------------------
# QueryProcessedEvent
# ---------------------------------------------------------------------------


class TestQueryRouting:
    @pytest.mark.asyncio
    async def test_records_query(self):
        listener, ledger = _make_listener()
        event = QueryProcessedEvent(
            organization_id=ORG_ID,
            queries=1,
            billable=True,
        )

        await listener.handle(event)

        assert ledger.recorded[(ORG_ID, ActionType.QUERIES)] == 1

    @pytest.mark.asyncio
    async def test_records_multiple_queries(self):
        listener, ledger = _make_listener()
        event = QueryProcessedEvent(
            organization_id=ORG_ID,
            queries=5,
            billable=True,
        )

        await listener.handle(event)

        assert ledger.recorded[(ORG_ID, ActionType.QUERIES)] == 5

    @pytest.mark.asyncio
    async def test_skips_non_billable_query(self):
        listener, ledger = _make_listener()
        event = QueryProcessedEvent(
            organization_id=ORG_ID,
            queries=1,
            billable=False,
        )

        await listener.handle(event)

        assert len(ledger.record_calls) == 0


# ---------------------------------------------------------------------------
# SyncLifecycleEvent — terminal events flush the ledger
# ---------------------------------------------------------------------------


class TestSyncLifecycleRouting:
    @pytest.mark.asyncio
    async def test_completed_flushes(self):
        listener, ledger = _make_listener()
        event = SyncLifecycleEvent.completed(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID,
            source_connection_id=SC_ID,
            source_type="slack",
            collection_name="test",
            collection_readable_id="test-col",
        )

        await listener.handle(event)

        assert ORG_ID in ledger.flushed_orgs

    @pytest.mark.asyncio
    async def test_failed_flushes(self):
        listener, ledger = _make_listener()
        event = SyncLifecycleEvent.failed(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID,
            source_connection_id=SC_ID,
            source_type="slack",
            collection_name="test",
            collection_readable_id="test-col",
            error="something broke",
        )

        await listener.handle(event)

        assert ORG_ID in ledger.flushed_orgs

    @pytest.mark.asyncio
    async def test_cancelled_flushes(self):
        listener, ledger = _make_listener()
        event = SyncLifecycleEvent.cancelled(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID,
            source_connection_id=SC_ID,
            source_type="slack",
            collection_name="test",
            collection_readable_id="test-col",
        )

        await listener.handle(event)

        assert ORG_ID in ledger.flushed_orgs

    @pytest.mark.asyncio
    async def test_running_does_not_flush(self):
        listener, ledger = _make_listener()
        event = SyncLifecycleEvent.running(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID,
            source_connection_id=SC_ID,
            source_type="slack",
            collection_name="test",
            collection_readable_id="test-col",
        )

        await listener.handle(event)

        assert len(ledger.flushed_orgs) == 0

    @pytest.mark.asyncio
    async def test_pending_does_not_flush(self):
        listener, ledger = _make_listener()
        event = SyncLifecycleEvent.pending(
            organization_id=ORG_ID,
            sync_id=SYNC_ID,
            sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID,
            source_connection_id=SC_ID,
            source_type="slack",
            collection_name="test",
            collection_readable_id="test-col",
        )

        await listener.handle(event)

        assert len(ledger.flushed_orgs) == 0


# ---------------------------------------------------------------------------
# SourceConnectionLifecycleEvent
# ---------------------------------------------------------------------------


class TestSourceConnectionRouting:
    @pytest.mark.asyncio
    async def test_created_records_plus_one(self):
        listener, ledger = _make_listener()
        event = SourceConnectionLifecycleEvent.created(
            organization_id=ORG_ID,
            source_connection_id=SC_ID,
            source_type="slack",
            collection_readable_id="test-col",
        )

        await listener.handle(event)

        assert ledger.recorded[(ORG_ID, ActionType.SOURCE_CONNECTIONS)] == 1

    @pytest.mark.asyncio
    async def test_deleted_records_minus_one(self):
        listener, ledger = _make_listener()
        event = SourceConnectionLifecycleEvent.deleted(
            organization_id=ORG_ID,
            source_connection_id=SC_ID,
            source_type="slack",
            collection_readable_id="test-col",
        )

        await listener.handle(event)

        assert ledger.recorded[(ORG_ID, ActionType.SOURCE_CONNECTIONS)] == -1

    @pytest.mark.asyncio
    async def test_auth_completed_is_ignored(self):
        """AUTH_COMPLETED is not a billable source connection event."""
        listener, ledger = _make_listener()
        event = SourceConnectionLifecycleEvent.auth_completed(
            organization_id=ORG_ID,
            source_connection_id=SC_ID,
            source_type="slack",
            collection_readable_id="test-col",
        )

        await listener.handle(event)

        assert len(ledger.record_calls) == 0


# ---------------------------------------------------------------------------
# Error handling — listener should not raise
# ---------------------------------------------------------------------------


class TestListenerErrorHandling:
    @pytest.mark.asyncio
    async def test_swallows_ledger_errors(self):
        """If the ledger raises, the listener logs but does not propagate."""

        class BrokenLedger(FakeUsageLedger):
            async def record(self, *args, **kwargs):
                raise RuntimeError("db connection lost")

        listener = UsageBillingListener(ledger=BrokenLedger())
        event = QueryProcessedEvent(
            organization_id=ORG_ID,
            queries=1,
            billable=True,
        )

        await listener.handle(event)


# ---------------------------------------------------------------------------
# EVENT_PATTERNS sanity check
# ---------------------------------------------------------------------------


class TestEventPatterns:
    def test_covers_expected_namespaces(self):
        patterns = UsageBillingListener.EVENT_PATTERNS
        assert "entity.*" in patterns
        assert "query.*" in patterns
        assert "sync.*" in patterns
        assert "source_connection.*" in patterns
