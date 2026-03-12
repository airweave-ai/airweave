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
        sync_id: str,
        sync_job_id: Optional[str],
        organization_id: str,
        force_full_sync: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Create sync job for scheduled runs or return existing ID.

        Returns dict with sync job info, or None if skipped.
        For manual runs (sync_job_id provided), returns {"id": sync_job_id}.
        """
        from airweave.platform.temporal.activities import create_sync_job_activity

        if sync_job_id is not None:
            return {"id": sync_job_id}

        try:
            timeout = timedelta(hours=1, minutes=5) if force_full_sync else timedelta(seconds=30)

            result = await workflow.execute_activity(
                create_sync_job_activity,
                args=[sync_id, organization_id, force_full_sync],
                start_to_close_timeout=timeout,
                heartbeat_timeout=timedelta(minutes=1) if force_full_sync else None,
                retry_policy=RetryPolicy(
                    maximum_attempts=1,
                ),
            )
        except Exception as e:
            workflow.logger.warning(f"Skipping scheduled run for sync {sync_id}: {str(e)}")
            return None

        if result and result.get("_skipped"):
            workflow.logger.info(
                f"Skipping scheduled run for sync {sync_id}: "
                f"{result.get('reason', 'already running')}"
            )
            return None

        return result

    @staticmethod
    def _normalize_args(args: tuple) -> tuple:
        """Backward-compat: convert old 7-dict payload to (sync_id, sync_job_id, org_id, force).

        Old schedules baked the full serialized dicts into their payload:
            (sync_dict, sync_job_dict, collection_dict, connection_dict,
             ctx_dict, access_token, force_full_sync)

        New format is just (sync_id, sync_job_id, organization_id, force_full_sync).
        Detect by checking whether the first arg is a dict.
        """
        if args and isinstance(args[0], dict):
            sync_dict = args[0]
            sync_job_dict = args[1] if len(args) > 1 else None
            ctx_dict = args[4] if len(args) > 4 else {}
            force = args[6] if len(args) > 6 else False

            sync_id = str(sync_dict["id"])
            sync_job_id = str(sync_job_dict["id"]) if sync_job_dict else None
            organization_id = str(ctx_dict.get("organization_id", ""))
            return sync_id, sync_job_id, organization_id, bool(force)

        sync_id = args[0] if len(args) > 0 else ""
        sync_job_id = args[1] if len(args) > 1 else None
        organization_id = args[2] if len(args) > 2 else ""
        force_full_sync = args[3] if len(args) > 3 else False
        return sync_id, sync_job_id, organization_id, bool(force_full_sync)

    @workflow.run
    async def run(self, *args) -> None:
        """Run the source connection sync workflow.

        Accepts both:
        - New format: (sync_id, sync_job_id, organization_id, force_full_sync)
        - Legacy format: (sync_dict, sync_job_dict, collection_dict,
          connection_dict, ctx_dict, access_token, force_full_sync)
        """
        sync_id, sync_job_id, organization_id, force_full_sync = self._normalize_args(args)

        if not sync_id or not organization_id:
            workflow.logger.error(
                f"Missing required IDs: sync_id={sync_id!r}, org={organization_id!r}"
            )
            return

        from airweave.platform.temporal.activities import (
            run_sync_activity,
            self_destruct_orphaned_sync_activity,
        )

        sync_job_result = await self._create_sync_job_if_needed(
            sync_id, sync_job_id, organization_id, force_full_sync
        )
        if sync_job_result is None:
            return

        if sync_job_result.get("_orphaned"):
            workflow.logger.info(
                f"Sync {sync_id} is orphaned. "
                f"Reason: {sync_job_result.get('reason', 'Unknown')}. "
                f"Initiating self-destruct cleanup..."
            )

            try:
                await workflow.execute_activity(
                    self_destruct_orphaned_sync_activity,
                    args=[
                        sync_id,
                        organization_id,
                        sync_job_result.get("reason", "Sync not found"),
                    ],
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
                workflow.logger.info(f"Self-destruct cleanup complete for sync {sync_id}")
            except Exception as cleanup_error:
                workflow.logger.warning(
                    f"Self-destruct cleanup error: {cleanup_error}. Continuing graceful exit."
                )

            return

        sync_job_id = sync_job_result["id"]

        try:
            await workflow.execute_activity(
                run_sync_activity,
                args=[
                    sync_id,
                    sync_job_id,
                    organization_id,
                    force_full_sync,
                ],
                start_to_close_timeout=timedelta(days=7),
                heartbeat_timeout=timedelta(minutes=15),
                cancellation_type=workflow.ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
                retry_policy=RetryPolicy(
                    maximum_attempts=1,
                ),
            )

        except Exception as e:
            error_str = str(e)
            if hasattr(e, "__cause__") and e.__cause__:
                error_str += f" {str(e.__cause__)}"

            workflow.logger.debug(f"Activity exception - str: {error_str}")
            workflow.logger.debug(f"Activity exception type: {type(e).__name__}")

            if "ORPHANED_SYNC" in error_str:
                workflow.logger.info(
                    f"Sync {sync_id} became orphaned during execution. "
                    f"Source connection was deleted. Initiating self-destruct cleanup..."
                )

                try:
                    await workflow.execute_activity(
                        self_destruct_orphaned_sync_activity,
                        args=[
                            sync_id,
                            organization_id,
                            "Source connection deleted during sync execution",
                        ],
                        start_to_close_timeout=timedelta(minutes=5),
                        retry_policy=RetryPolicy(maximum_attempts=3),
                    )
                    workflow.logger.info(f"Self-destruct cleanup complete for sync {sync_id}")
                except Exception as cleanup_error:
                    workflow.logger.warning(
                        f"Self-destruct cleanup error: {cleanup_error}. Continuing graceful exit."
                    )

                return

            if isinstance(e, asyncio.CancelledError):
                from airweave.platform.temporal.activities import mark_sync_job_cancelled_activity

                reason = f"{type(e).__name__}: {e}"
                try:
                    await asyncio.shield(
                        workflow.execute_activity(
                            mark_sync_job_cancelled_activity,
                            args=[
                                sync_job_id,
                                organization_id,
                                reason,
                                workflow.now().replace(tzinfo=None).isoformat(),
                            ],
                            start_to_close_timeout=timedelta(seconds=30),
                            cancellation_type=workflow.ActivityCancellationType.ABANDON,
                        )
                    )
                finally:
                    raise

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
