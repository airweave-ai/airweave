"""Temporal workflow for API key cleanup and maintenance."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from airweave.domains.temporal.activities import (
        cleanup_revoked_keys_activity,
        expire_past_due_keys_activity,
        prune_usage_log_activity,
    )


@workflow.defn
class APIKeyCleanupWorkflow:
    """Workflow that runs all API key maintenance activities sequentially.

    1. Expire active keys past their expiration date
    2. Delete revoked keys past the 90-day retention period
    3. Prune usage log entries older than 90 days
    """

    @workflow.run
    async def run(self) -> dict[str, int]:
        """Execute all cleanup activities.

        Returns:
            Counts of affected records per activity.
        """
        retry_policy = RetryPolicy(
            maximum_attempts=3,
            initial_interval=timedelta(seconds=10),
            maximum_interval=timedelta(minutes=1),
            backoff_coefficient=2.0,
        )

        expired_result = await workflow.execute_activity(
            expire_past_due_keys_activity,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=retry_policy,
        )

        revoked_result = await workflow.execute_activity(
            cleanup_revoked_keys_activity,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=retry_policy,
        )

        pruned_result = await workflow.execute_activity(
            prune_usage_log_activity,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )

        return {
            "expired": expired_result["expired"],
            "deleted": revoked_result["deleted"],
            "delete_errors": revoked_result["errors"],
            "usage_log_pruned": pruned_result["pruned"],
        }
