"""Tests for SyncOrchestrator exception paths and heartbeat publication."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.domains.sync_pipeline.orchestrator import SyncOrchestrator


def _make_sync_context(sync_id=None, sync_job_id=None, org_id=None):
    ctx = MagicMock()
    ctx.sync = SimpleNamespace(id=sync_id or uuid4())
    ctx.sync_job = SimpleNamespace(id=sync_job_id or uuid4())
    ctx.organization = SimpleNamespace(id=org_id or uuid4())
    ctx.organization_id = ctx.organization.id
    ctx.sync_job.id = ctx.sync_job.id
    ctx.source_connection_id = uuid4()
    ctx.source_short_name = "test_source"
    ctx.should_batch = False
    ctx.batch_size = 10
    ctx.max_batch_latency_ms = 100
    ctx.logger = MagicMock()
    return ctx


def _make_orchestrator(**overrides):
    sync_context = overrides.pop("sync_context", _make_sync_context())
    worker_pool = overrides.pop("worker_pool", MagicMock())
    worker_pool.max_workers = 4

    usage_ledger = overrides.pop("usage_ledger", MagicMock())
    if not hasattr(usage_ledger, "flush") or not callable(usage_ledger.flush):
        usage_ledger.flush = AsyncMock()

    usage_checker = overrides.pop("usage_checker", MagicMock())

    return SyncOrchestrator(
        entity_pipeline=overrides.pop("entity_pipeline", MagicMock()),
        worker_pool=worker_pool,
        stream=overrides.pop("stream", MagicMock()),
        sync_context=sync_context,
        runtime=overrides.pop("runtime", MagicMock()),
        access_control_pipeline=overrides.pop("access_control_pipeline", MagicMock()),
        event_bus=overrides.pop("event_bus", MagicMock()),
        usage_checker=usage_checker,
        usage_ledger=usage_ledger,
    )


class TestUsageLedgerFlushFailure:
    @pytest.mark.asyncio
    async def test_flush_failure_does_not_mask_original_exception(self):
        """If _usage_ledger.flush raises inside finally, original exception still propagates."""
        from airweave.domains.sync_pipeline.exceptions import SyncFailureError

        usage_ledger = MagicMock()
        usage_ledger.flush = AsyncMock(side_effect=RuntimeError("redis down"))

        orc = _make_orchestrator(usage_ledger=usage_ledger)

        with (
            patch.object(orc, "_start_sync", new_callable=AsyncMock, side_effect=SyncFailureError("source failed")),
            patch.object(orc, "_handle_sync_failure", new_callable=AsyncMock),
            patch.object(orc, "entity_pipeline", MagicMock()),
            patch(
                "airweave.domains.sync_pipeline.orchestrator.worker_metrics",
                create=True,
            ),
        ):
            with pytest.raises(SyncFailureError, match="source failed"):
                await orc.run()

        orc.sync_context.logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_flush_is_attempted_in_finally_after_success_path(self):
        """Even on successful sync, flush is called exactly once."""
        usage_ledger = MagicMock()
        usage_ledger.flush = AsyncMock()

        orc = _make_orchestrator(usage_ledger=usage_ledger)

        with (
            patch.object(orc, "_start_sync", new_callable=AsyncMock),
            patch.object(orc, "_process_entities", new_callable=AsyncMock),
            patch.object(orc, "_source_supports_access_control", return_value=False),
            patch.object(orc, "_cleanup_orphaned_entities_if_needed", new_callable=AsyncMock),
            patch.object(orc, "_complete_sync", new_callable=AsyncMock),
            patch.object(orc, "entity_pipeline", MagicMock()),
        ):
            await orc.run()

        usage_ledger.flush.assert_awaited_once_with(orc.sync_context.organization.id)


class TestPublishAclHeartbeat:
    @pytest.mark.asyncio
    async def test_publishes_correct_event(self):
        """_publish_acl_heartbeat publishes AccessControlMembershipBatchProcessedEvent."""
        from airweave.core.events.sync import AccessControlMembershipBatchProcessedEvent

        event_bus = MagicMock()
        event_bus.publish = AsyncMock()

        orc = _make_orchestrator(event_bus=event_bus)

        await orc._publish_acl_heartbeat()

        event_bus.publish.assert_awaited_once()
        event = event_bus.publish.call_args[0][0]
        assert isinstance(event, AccessControlMembershipBatchProcessedEvent)
        assert event.sync_id == orc.sync_context.sync.id
        assert event.organization_id == orc.sync_context.organization_id
