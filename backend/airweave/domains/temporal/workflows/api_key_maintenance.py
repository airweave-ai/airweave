"""Temporal workflow for daily API key lifecycle maintenance.

A single deterministically-ordered workflow ensures notifications
run while keys are still ACTIVE, before expire transitions them
to EXPIRED.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn
class APIKeyMaintenanceWorkflow:
    """Daily API key lifecycle: notify, expire, cleanup, prune.

    Activity ordering is deliberate:
    1. Notify — while keys are still ACTIVE
    2. Expire — transition past-due ACTIVE → EXPIRED
    3. Cleanup — delete revoked keys past retention
    4. Prune — delete old usage log rows
    """

    @workflow.run
    async def run(self) -> dict[str, int]:
        """Execute all API key maintenance activities in order.

        Returns:
            Merged counts from all four activities.
        """
        retry_policy = RetryPolicy(
            maximum_attempts=3,
            initial_interval=timedelta(seconds=10),
            maximum_interval=timedelta(minutes=1),
            backoff_coefficient=2.0,
        )

        notify_result: dict[str, int] = await workflow.execute_activity(
            "check_and_notify_expiring_keys_activity",
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )

        expired_result: dict[str, int] = await workflow.execute_activity(
            "expire_past_due_keys_activity",
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=retry_policy,
        )

        revoked_result: dict[str, int] = await workflow.execute_activity(
            "cleanup_revoked_keys_activity",
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=retry_policy,
        )

        pruned_result: dict[str, int] = await workflow.execute_activity(
            "prune_usage_log_activity",
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=retry_policy,
        )

        return {
            **notify_result,
            "expired": expired_result["expired"],
            "deleted": revoked_result["deleted"],
            "delete_errors": revoked_result["errors"],
            "usage_log_pruned": pruned_result["pruned"],
        }
