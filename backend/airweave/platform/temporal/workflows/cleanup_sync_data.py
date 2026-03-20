"""Temporal workflow for cleaning up external data after sync deletion."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from airweave.platform.temporal.activities import cleanup_sync_data_activity

_CLEANUP_TIMEOUT = timedelta(minutes=15)
_CLEANUP_RETRIES = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=10),
    maximum_interval=timedelta(minutes=2),
    backoff_coefficient=2.0,
)


@workflow.defn
class CleanupSyncDataWorkflow:
    """Async cleanup of external data (Vespa, ARF) after sync deletion.

    Runs after DB records have been cascade-deleted.
    Only accepts primitive IDs to keep the Temporal payload small.
    """

    @workflow.run
    async def run(
        self,
        sync_ids: list[str],
        collection_id: str,
        organization_id: str,
    ) -> Dict[str, Any]:
        """Run cleanup for external sync data."""
        return await workflow.execute_activity(
            cleanup_sync_data_activity,
            args=[sync_ids, collection_id, organization_id],
            start_to_close_timeout=_CLEANUP_TIMEOUT,
            retry_policy=_CLEANUP_RETRIES,
        )
