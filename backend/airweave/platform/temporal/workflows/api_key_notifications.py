"""Temporal workflow for API key expiration notifications."""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from airweave.platform.temporal.activities import (
        check_and_notify_expiring_keys_activity,
    )


@workflow.defn
class APIKeyExpirationCheckWorkflow:
    """Workflow that checks for expiring API keys and sends notifications."""

    @workflow.run
    async def run(self) -> dict[str, int]:
        """Execute the API key expiration check and notification workflow.

        Returns:
        -------
            dict[str, int]: Counts of notifications sent by type

        """
        return await workflow.execute_activity(
            check_and_notify_expiring_keys_activity,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=10),
                maximum_interval=timedelta(minutes=1),
                backoff_coefficient=2.0,
            ),
        )
