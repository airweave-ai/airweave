"""Temporal workflows for Airweave."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, Dict, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn
class RunSourceConnectionWorkflow:
    """Workflow for running a source connection sync."""

    async def _create_sync_job_if_needed(
        self,
        sync_dict: Dict[str, Any],
        sync_job_dict: Optional[Dict[str, Any]],
        ctx_dict: Dict[str, Any],
        force_full_sync: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Create sync job for scheduled runs or return existing one."""
        from airweave.platform.temporal.activities import create_sync_job_activity

        # If no sync_job_dict provided (scheduled run), create a new sync job
        if sync_job_dict is None:
            sync_id = sync_dict.get("id")
            try:
                # For forced full sync (daily cleanup), use longer timeout to allow waiting
                timeout = (
                    timedelta(hours=1, minutes=5) if force_full_sync else timedelta(seconds=30)
                )

                sync_job_dict = await workflow.execute_activity(
                    create_sync_job_activity,
                    args=[sync_id, ctx_dict, force_full_sync],
                    start_to_close_timeout=timeout,
                    heartbeat_timeout=timedelta(minutes=1) if force_full_sync else None,
                    retry_policy=RetryPolicy(
                        maximum_attempts=1,  # NO RETRIES - fail fast
                    ),
                )
            except Exception as e:
                # If we can't create a sync job (e.g., one is already running), skip this run
                workflow.logger.warning(f"Skipping scheduled run for sync {sync_id}: {str(e)}")
                return None  # Signal to exit gracefully
        return sync_job_dict

    @workflow.run
    async def run(
        self,
        sync_dict: Dict[str, Any],
        sync_job_dict: Optional[Dict[str, Any]],  # Made optional for scheduled runs
        collection_dict: Dict[str, Any],
        connection_dict: Dict[str, Any],  # Connection schema, NOT SourceConnection
        ctx_dict: Dict[str, Any],
        access_token: Optional[str] = None,
        force_full_sync: bool = False,  # Force full sync with deletion
    ) -> None:
        """Run the source connection sync workflow.

        Args:
            sync_dict: The sync configuration as dict
            sync_job_dict: The sync job as dict (optional for scheduled runs)
            collection_dict: The collection as dict
            connection_dict: The connection as dict (Connection schema, NOT SourceConnection)
            ctx_dict: The API context as dict
            access_token: Optional access token
            force_full_sync: If True, forces a full sync with orphaned entity deletion
        """
        from airweave.platform.temporal.activities import (
            run_sync_activity,
            self_destruct_orphaned_sync_activity,
        )

        # Create sync job if needed (for scheduled runs)
        sync_job_dict = await self._create_sync_job_if_needed(
            sync_dict, sync_job_dict, ctx_dict, force_full_sync
        )
        if sync_job_dict is None:
            return  # Exit gracefully if we couldn't create a job

        # Check if sync is orphaned (deleted during workflow queueing)
        if sync_job_dict.get("_orphaned"):
            workflow.logger.info(
                f"🧹 Sync {sync_dict['id']} is orphaned. "
                f"Reason: {sync_job_dict.get('reason', 'Unknown')}. "
                f"Initiating self-destruct cleanup..."
            )

            # Self-destruct: clean up any remaining schedules
            try:
                await workflow.execute_activity(
                    self_destruct_orphaned_sync_activity,
                    args=[
                        sync_dict["id"],
                        ctx_dict,
                        sync_job_dict.get("reason", "Sync not found"),
                    ],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
                workflow.logger.info(
                    f"✅ Self-destruct cleanup complete for sync {sync_dict['id']}"
                )
            except Exception as cleanup_error:
                workflow.logger.warning(
                    f"⚠️ Self-destruct cleanup encountered an error: {cleanup_error}. "
                    f"Continuing graceful exit."
                )

            return  # Exit gracefully without error

        try:
            # Use longer heartbeat timeout in local development for debugging
            local_development = ctx_dict.get("local_development", False)
            heartbeat_timeout = timedelta(hours=1) if local_development else timedelta(minutes=15)

            await workflow.execute_activity(
                run_sync_activity,
                args=[
                    sync_dict,
                    sync_job_dict,
                    collection_dict,
                    connection_dict,
                    ctx_dict,
                    access_token,
                    force_full_sync,
                ],
                start_to_close_timeout=timedelta(days=7),
                heartbeat_timeout=heartbeat_timeout,
                cancellation_type=workflow.ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
                retry_policy=RetryPolicy(
                    maximum_attempts=1,  # NO RETRIES - fail fast
                ),
            )

        except Exception as e:
            # Check if this is an orphaned sync error (source connection deleted mid-execution)
            # Check both str(e) and the exception's cause chain for the ORPHANED_SYNC marker
            error_str = str(e)
            if hasattr(e, "__cause__") and e.__cause__:
                error_str += f" {str(e.__cause__)}"

            # Log the full error for debugging
            workflow.logger.debug(f"Activity exception - str: {error_str}")
            workflow.logger.debug(f"Activity exception type: {type(e).__name__}")

            if "ORPHANED_SYNC" in error_str:
                workflow.logger.info(
                    f"🧹 Sync {sync_dict['id']} became orphaned during execution. "
                    f"Source connection was deleted. Initiating self-destruct cleanup..."
                )

                # Self-destruct: clean up any remaining schedules
                try:
                    await workflow.execute_activity(
                        self_destruct_orphaned_sync_activity,
                        args=[
                            sync_dict["id"],
                            ctx_dict,
                            "Source connection deleted during sync execution",
                        ],
                        start_to_close_timeout=timedelta(minutes=5),
                        retry_policy=RetryPolicy(maximum_attempts=3),
                    )
                    workflow.logger.info(
                        f"✅ Self-destruct cleanup complete for sync {sync_dict['id']}"
                    )
                except Exception as cleanup_error:
                    workflow.logger.warning(
                        f"⚠️ Self-destruct cleanup encountered an error: {cleanup_error}. "
                        f"Continuing graceful exit."
                    )

                return  # Exit gracefully without error

            # For CancelledError, need to mark job as cancelled before re-raising
            if isinstance(e, asyncio.CancelledError):
                # ensure DB gets updated even though the workflow was cancelled
                from airweave.platform.temporal.activities import mark_sync_job_cancelled_activity

                reason = f"{type(e).__name__}: {e}"
                try:
                    await asyncio.shield(
                        workflow.execute_activity(
                            mark_sync_job_cancelled_activity,
                            args=[
                                str(sync_job_dict["id"]),
                                ctx_dict,
                                reason,
                                workflow.now().replace(tzinfo=None).isoformat(),
                            ],
                            start_to_close_timeout=timedelta(seconds=30),
                            # fire-and-forget semantics on the server side
                            cancellation_type=workflow.ActivityCancellationType.ABANDON,
                        )
                    )
                finally:
                    # keep Workflow result as CANCELED
                    raise

            # All other exceptions should be re-raised
            raise


@workflow.defn
class CleanupStuckSyncJobsWorkflow:
    """Workflow for cleaning up stuck sync jobs."""

    @workflow.run
    async def run(self) -> None:
        """Run the cleanup workflow to detect and cancel stuck sync jobs.

        This workflow is scheduled to run periodically (every 150 seconds) to:
        - Cancel jobs stuck in CANCELLING/PENDING for > 3 minutes
        - Cancel jobs in RUNNING for > 10 minutes with no entity updates
        """
        from airweave.platform.temporal.activities import cleanup_stuck_sync_jobs_activity

        await workflow.execute_activity(
            cleanup_stuck_sync_jobs_activity,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=10),
                maximum_interval=timedelta(seconds=60),
            ),
        )


@workflow.defn
class CleanupSyncDataWorkflow:
    """Workflow for cleaning up external data (Vespa, ARF) after sync deletion.

    This runs asynchronously after the DB records have been cascade-deleted,
    handling the potentially slow cleanup of destination data. Vespa deletions
    can take minutes, so this must not run in the API request cycle.

    Only accepts primitive IDs to keep the Temporal payload small.
    """

    @workflow.run
    async def run(
        self,
        sync_ids: list[str],
        collection_id: str,
        organization_id: str,
    ) -> Dict[str, Any]:
        """Run cleanup for external sync data.

        Args:
            sync_ids: List of sync ID strings to clean up.
            collection_id: Collection UUID string.
            organization_id: Organization UUID string.

        Returns:
            Summary dict from the cleanup activity.
        """
        from airweave.platform.temporal.activities import cleanup_sync_data_activity

        return await workflow.execute_activity(
            cleanup_sync_data_activity,
            args=[sync_ids, collection_id, organization_id],
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=10),
                maximum_interval=timedelta(minutes=2),
                backoff_coefficient=2.0,
            ),
        )
