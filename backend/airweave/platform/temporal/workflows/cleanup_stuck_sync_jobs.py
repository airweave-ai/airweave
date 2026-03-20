"""Temporal workflow for cleaning up stuck sync jobs."""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from airweave.platform.temporal.activities import cleanup_stuck_sync_jobs_activity

_CLEANUP_TIMEOUT = timedelta(minutes=5)
_CLEANUP_RETRIES = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=10),
    maximum_interval=timedelta(seconds=60),
)


@workflow.defn
class CleanupStuckSyncJobsWorkflow:
    """Periodic workflow to detect and cancel stuck sync jobs.

    Scheduled to run every ~150 seconds. Cancels jobs that are:
    - Stuck in CANCELLING/PENDING for > 3 minutes
    - In RUNNING for > 10 minutes with no entity updates
    """

    @workflow.run
    async def run(self) -> None:
        """Detect and cancel stuck sync jobs."""
        await workflow.execute_activity(
            cleanup_stuck_sync_jobs_activity,
            start_to_close_timeout=_CLEANUP_TIMEOUT,
            retry_policy=_CLEANUP_RETRIES,
        )
