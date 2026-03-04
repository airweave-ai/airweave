"""Integration tests for the usage logging pipeline.

Wires the real components together — EventBus → UsageBillingListener →
UsageLedger → FakeUsageRepository — and drives realistic scenarios through.
Asserts that the final usage numbers in the repository are correct.

These tests answer: "if a sync processes N entities and a user runs M searches,
do the numbers in the usage table come out right?"
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from airweave.adapters.event_bus.fake import FakeEventBus
from airweave.core.events.enums import SourceConnectionEventType, SyncEventType
from airweave.core.events.source_connection import SourceConnectionLifecycleEvent
from airweave.core.events.sync import (
    EntityBatchProcessedEvent,
    QueryProcessedEvent,
    SyncLifecycleEvent,
)
from airweave.domains.billing.fakes.repository import (
    FakeBillingPeriodRepository,
    FakeOrganizationBillingRepository,
)
from airweave.domains.usage.fakes.repository import FakeUsageRepository
from airweave.domains.usage.ledger import UsageLedger
from airweave.domains.usage.subscribers.billing_listener import UsageBillingListener
from airweave.domains.usage.tests.conftest import (
    _make_billing_model,
    _make_period_model,
    _make_usage_model,
)
from airweave.domains.usage.types import ActionType

ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
SYNC_ID = uuid4()
JOB_ID = uuid4()
COLLECTION_ID = uuid4()
SC_ID = uuid4()


@asynccontextmanager
async def _fake_db_context():
    yield AsyncMock()


def _build_pipeline(org_id: UUID = ORG_ID):
    """Wire the full usage pipeline with fakes at the edges.

    Returns (event_bus, usage_repo) so tests can publish events
    and then inspect the final usage state.
    """
    usage_repo = FakeUsageRepository()
    billing_repo = FakeOrganizationBillingRepository()
    period_repo = FakeBillingPeriodRepository()

    billing = _make_billing_model(org_id=org_id)
    billing_repo.seed(org_id, billing)
    period = _make_period_model(org_id=org_id)
    period_repo.seed(period)
    usage = _make_usage_model(org_id=org_id, billing_period_id=period.id)
    usage_repo.seed_current(org_id, usage)

    ledger = UsageLedger(
        usage_repo=usage_repo,
        billing_repo=billing_repo,
        period_repo=period_repo,
    )

    listener = UsageBillingListener(ledger=ledger)

    bus = FakeEventBus(call_subscribers=True)
    for pattern in listener.EVENT_PATTERNS:
        bus.subscribe(pattern, listener.handle)

    return bus, usage_repo, ledger


# ---------------------------------------------------------------------------
# Scenario: a sync processes 3 batches, then completes
# ---------------------------------------------------------------------------


@patch("airweave.db.session.get_db_context", _fake_db_context)
class TestSyncEntityAccounting:
    @pytest.mark.asyncio
    async def test_three_batches_then_complete(self):
        """Simulate a realistic sync: 3 entity batches → completed.

        Batch 1: 40 inserted, 10 updated
        Batch 2: 30 inserted, 20 updated
        Batch 3: 25 inserted,  5 updated
        Total billable: 130
        """
        bus, usage_repo, _ = _build_pipeline()

        await bus.publish(SyncLifecycleEvent.running(
            organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            source_type="slack", collection_name="test", collection_readable_id="test-col",
        ))

        batches = [(40, 10, 5, 3), (30, 20, 2, 8), (25, 5, 0, 12)]
        for inserted, updated, deleted, kept in batches:
            await bus.publish(EntityBatchProcessedEvent(
                organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
                collection_id=COLLECTION_ID, source_connection_id=SC_ID,
                inserted=inserted, updated=updated, deleted=deleted, kept=kept,
                billable=True,
            ))

        await bus.publish(SyncLifecycleEvent.completed(
            organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            source_type="slack", collection_name="test", collection_readable_id="test-col",
        ))

        current = usage_repo._current[ORG_ID]
        assert current.entities == 130  # (40+10) + (30+20) + (25+5)

    @pytest.mark.asyncio
    async def test_deleted_and_kept_not_billed(self):
        """Only inserted + updated are billable. Deleted/kept must not affect the count."""
        bus, usage_repo, _ = _build_pipeline()

        await bus.publish(SyncLifecycleEvent.running(
            organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            source_type="stub", collection_name="test", collection_readable_id="test-col",
        ))

        await bus.publish(EntityBatchProcessedEvent(
            organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            inserted=10, updated=5, deleted=500, kept=1000,
            billable=True,
        ))

        await bus.publish(SyncLifecycleEvent.completed(
            organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            source_type="stub", collection_name="test", collection_readable_id="test-col",
        ))

        current = usage_repo._current[ORG_ID]
        assert current.entities == 15  # NOT 1515

    @pytest.mark.asyncio
    async def test_non_billable_batches_ignored(self):
        """Batches with billable=False must not contribute to usage."""
        bus, usage_repo, _ = _build_pipeline()

        await bus.publish(SyncLifecycleEvent.running(
            organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            source_type="stub", collection_name="test", collection_readable_id="test-col",
        ))

        await bus.publish(EntityBatchProcessedEvent(
            organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            inserted=100, updated=50, billable=True,
        ))
        await bus.publish(EntityBatchProcessedEvent(
            organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            inserted=999, updated=999, billable=False,
        ))

        await bus.publish(SyncLifecycleEvent.completed(
            organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            source_type="stub", collection_name="test", collection_readable_id="test-col",
        ))

        current = usage_repo._current[ORG_ID]
        assert current.entities == 150  # only the billable batch

    @pytest.mark.asyncio
    async def test_flush_on_completion_captures_sub_threshold(self):
        """A small batch below the flush threshold (100) must still be
        persisted when the sync completes, because the terminal event
        triggers ledger.flush().
        """
        bus, usage_repo, _ = _build_pipeline()

        await bus.publish(SyncLifecycleEvent.running(
            organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            source_type="stub", collection_name="test", collection_readable_id="test-col",
        ))

        await bus.publish(EntityBatchProcessedEvent(
            organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            inserted=7, updated=3, billable=True,
        ))

        # 10 entities — below entity threshold of 100, not auto-flushed
        assert usage_repo.call_count("increment_usage") == 0

        await bus.publish(SyncLifecycleEvent.completed(
            organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            source_type="stub", collection_name="test", collection_readable_id="test-col",
        ))

        current = usage_repo._current[ORG_ID]
        assert current.entities == 10

    @pytest.mark.asyncio
    async def test_failed_sync_still_flushes(self):
        """Even if a sync fails, the entities processed so far must be billed."""
        bus, usage_repo, _ = _build_pipeline()

        await bus.publish(SyncLifecycleEvent.running(
            organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            source_type="stub", collection_name="test", collection_readable_id="test-col",
        ))

        await bus.publish(EntityBatchProcessedEvent(
            organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            inserted=20, updated=5, billable=True,
        ))

        await bus.publish(SyncLifecycleEvent.failed(
            organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            source_type="stub", collection_name="test", collection_readable_id="test-col",
            error="connection lost",
        ))

        current = usage_repo._current[ORG_ID]
        assert current.entities == 25


# ---------------------------------------------------------------------------
# Scenario: search queries
# ---------------------------------------------------------------------------


@patch("airweave.db.session.get_db_context", _fake_db_context)
class TestQueryAccounting:
    @pytest.mark.asyncio
    async def test_fifteen_searches(self):
        """15 individual searches must result in query count = 15."""
        bus, usage_repo, ledger = _build_pipeline()

        for _ in range(15):
            await bus.publish(QueryProcessedEvent(
                organization_id=ORG_ID, queries=1, billable=True,
            ))

        # Query threshold is 10 — first 10 trigger auto-flush, remaining 5 are pending
        await ledger.flush(ORG_ID)

        current = usage_repo._current[ORG_ID]
        assert current.queries == 15

    @pytest.mark.asyncio
    async def test_non_billable_queries_not_counted(self):
        bus, usage_repo, ledger = _build_pipeline()

        for _ in range(5):
            await bus.publish(QueryProcessedEvent(
                organization_id=ORG_ID, queries=1, billable=True,
            ))
        for _ in range(10):
            await bus.publish(QueryProcessedEvent(
                organization_id=ORG_ID, queries=1, billable=False,
            ))

        await ledger.flush(ORG_ID)

        current = usage_repo._current[ORG_ID]
        assert current.queries == 5


# ---------------------------------------------------------------------------
# Scenario: mixed sync + search in the same billing period
# ---------------------------------------------------------------------------


@patch("airweave.db.session.get_db_context", _fake_db_context)
class TestMixedUsage:
    @pytest.mark.asyncio
    async def test_entities_and_queries_tracked_independently(self):
        bus, usage_repo, _ = _build_pipeline()

        # A sync that processes 200 entities (crosses threshold, auto-flushed)
        await bus.publish(SyncLifecycleEvent.running(
            organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            source_type="stub", collection_name="test", collection_readable_id="test-col",
        ))
        await bus.publish(EntityBatchProcessedEvent(
            organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            inserted=120, updated=80, billable=True,
        ))
        await bus.publish(SyncLifecycleEvent.completed(
            organization_id=ORG_ID, sync_id=SYNC_ID, sync_job_id=JOB_ID,
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            source_type="stub", collection_name="test", collection_readable_id="test-col",
        ))

        # Then 12 searches (crosses query threshold of 10)
        for _ in range(12):
            await bus.publish(QueryProcessedEvent(
                organization_id=ORG_ID, queries=1, billable=True,
            ))

        # 12 queries: 10 auto-flushed + 2 pending; use another terminal event to flush
        await bus.publish(SyncLifecycleEvent.completed(
            organization_id=ORG_ID, sync_id=uuid4(), sync_job_id=uuid4(),
            collection_id=COLLECTION_ID, source_connection_id=SC_ID,
            source_type="stub", collection_name="test", collection_readable_id="test-col",
        ))

        current = usage_repo._current[ORG_ID]
        assert current.entities == 200
        assert current.queries == 12
