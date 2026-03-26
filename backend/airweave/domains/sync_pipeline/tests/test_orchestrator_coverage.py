"""Coverage tests for SyncOrchestrator — missing state_machine.transition lines."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from airweave import schemas
from airweave.core.shared_models import ConnectionStatus, IntegrationType, SyncJobStatus
from airweave.domains.sync_pipeline.contexts.sync import SyncContext
from airweave.domains.sync_pipeline.orchestrator import SyncOrchestrator
from airweave.domains.sync_pipeline.pipeline.entity_tracker import SyncStats

MODULE = "airweave.domains.sync_pipeline.orchestrator"

ORG_ID = UUID("00000000-0000-0000-0000-000000000001")
SYNC_ID = UUID("00000000-0000-0000-0000-000000000010")
SYNC_JOB_ID = UUID("00000000-0000-0000-0000-000000000020")
COLLECTION_ID = UUID("00000000-0000-0000-0000-000000000030")
CONNECTION_ID = UUID("00000000-0000-0000-0000-000000000040")
SC_ID = UUID("00000000-0000-0000-0000-000000000050")
VDB_META_ID = UUID("00000000-0000-0000-0000-000000000060")
TS = datetime(2025, 1, 1, tzinfo=timezone.utc)
TS_NAIVE = datetime(2025, 1, 1)


def _make_sync_context() -> SyncContext:
    org = schemas.Organization(id=ORG_ID, name="Test", created_at=TS, modified_at=TS)
    sync = schemas.Sync(
        id=SYNC_ID,
        name="test",
        status="active",
        source_connection_id=CONNECTION_ID,
        destination_connection_ids=[CONNECTION_ID],
        organization_id=ORG_ID,
        created_at=TS,
        modified_at=TS,
    )
    sync_job = schemas.SyncJob(
        id=SYNC_JOB_ID,
        sync_id=SYNC_ID,
        status="running",
        organization_id=ORG_ID,
        created_at=TS,
        modified_at=TS,
        started_at=TS_NAIVE,
    )
    collection = schemas.CollectionRecord(
        id=COLLECTION_ID,
        name="test-collection",
        readable_id="test-collection",
        vector_db_deployment_metadata_id=VDB_META_ID,
        organization_id=ORG_ID,
        created_at=TS,
        modified_at=TS,
    )
    connection = schemas.Connection(
        id=CONNECTION_ID,
        name="test-conn",
        readable_id="test-conn",
        short_name="test_source",
        integration_type=IntegrationType.SOURCE,
        status=ConnectionStatus.ACTIVE,
        organization_id=ORG_ID,
        created_at=TS,
        modified_at=TS,
    )
    return SyncContext(
        organization=org,
        sync_id=SYNC_ID,
        sync_job_id=SYNC_JOB_ID,
        collection_id=COLLECTION_ID,
        source_connection_id=SC_ID,
        sync=sync,
        sync_job=sync_job,
        collection=collection,
        connection=connection,
        source_short_name="test_source",
    )


class FakeStateMachine:
    def __init__(self):
        self.calls: list[dict] = []

    async def transition(self, **kwargs):
        self.calls.append(kwargs)
        return MagicMock(applied=True)


def _make_orchestrator(state_machine=None) -> tuple[SyncOrchestrator, FakeStateMachine]:
    sm = state_machine or FakeStateMachine()

    entity_pipeline = AsyncMock()
    entity_pipeline.cleanup_orphaned_entities = AsyncMock()
    entity_pipeline.cleanup_temp_files = AsyncMock()

    worker_pool = MagicMock()
    worker_pool.max_workers = 5
    worker_pool.submit = AsyncMock()
    worker_pool.cancel_all = AsyncMock()

    stream = AsyncMock()
    stream.start = AsyncMock()
    stream.stop = AsyncMock()
    stream.cancel = AsyncMock()

    async def empty_stream():
        return
        yield  # noqa: E275 — make it an async generator

    stream.get_entities = empty_stream

    runtime = MagicMock()
    runtime.source.source_name = "test_source"
    runtime.source.short_name = "test_source"
    runtime.source.supports_access_control = False
    runtime.cursor = None
    runtime.entity_tracker.get_stats.return_value = SyncStats()
    runtime.entity_tracker.record_skipped = AsyncMock()

    ctx = _make_sync_context()

    event_bus = AsyncMock()
    usage_checker = AsyncMock()
    usage_ledger = AsyncMock()
    sync_cursor_service = AsyncMock()
    access_control_pipeline = AsyncMock()

    orch = SyncOrchestrator(
        entity_pipeline=entity_pipeline,
        worker_pool=worker_pool,
        stream=stream,
        sync_context=ctx,
        runtime=runtime,
        access_control_pipeline=access_control_pipeline,
        event_bus=event_bus,
        usage_checker=usage_checker,
        usage_ledger=usage_ledger,
        sync_cursor_service=sync_cursor_service,
        state_machine=sm,
        lifecycle_data=MagicMock(),
        sync_state_machine=MagicMock(),
    )
    return orch, sm


@pytest.mark.unit
async def test_start_sync_calls_state_machine_transition():
    """_start_sync calls state_machine.transition with RUNNING."""
    orch, sm = _make_orchestrator()

    await orch._start_sync()

    assert len(sm.calls) == 1
    assert sm.calls[0]["target"] == SyncJobStatus.RUNNING


@pytest.mark.unit
async def test_complete_sync_calls_state_machine_transition():
    """_complete_sync calls state_machine.transition with COMPLETED."""
    orch, sm = _make_orchestrator()

    with (
        patch(f"{MODULE}.get_db_context", AsyncMock()),
        patch(f"{MODULE}.business_events"),
    ):
        await orch._complete_sync()

    assert any(c["target"] == SyncJobStatus.COMPLETED for c in sm.calls)


@pytest.mark.unit
async def test_handle_sync_failure_calls_state_machine_transition():
    """_handle_sync_failure calls state_machine.transition with FAILED."""
    orch, sm = _make_orchestrator()

    with patch(f"{MODULE}.business_events"):
        await orch._handle_sync_failure(RuntimeError("test error"))

    assert any(c["target"] == SyncJobStatus.FAILED for c in sm.calls)


@pytest.mark.unit
async def test_handle_cancellation_calls_state_machine_transition():
    """_handle_cancellation calls state_machine.transition with CANCELLED."""
    orch, sm = _make_orchestrator()

    with patch(f"{MODULE}.business_events"):
        await orch._handle_cancellation()

    assert any(c["target"] == SyncJobStatus.CANCELLED for c in sm.calls)
