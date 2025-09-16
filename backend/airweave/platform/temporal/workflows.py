"""Temporal workflows for Airweave."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, Dict, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import is_cancelled_exception


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
                        maximum_attempts=1,  # Don't retry if job already exists
                        initial_interval=timedelta(seconds=1),
                    ),
                )
            except Exception as e:
                # If we can't create a sync job (e.g., one is already running), skip this run
                ctx_dict["logger"].warning(f"Skipping scheduled run for sync {sync_id}: {str(e)}")
                return None  # Signal to exit gracefully
        return sync_job_dict

    @workflow.run
    async def run(
        self,
        sync_dict: Dict[str, Any],
        sync_job_dict: Optional[Dict[str, Any]],  # Made optional for scheduled runs
        sync_dag_dict: Dict[str, Any],
        collection_dict: Dict[str, Any],
        source_connection_dict: Dict[str, Any],
        ctx_dict: Dict[str, Any],
        access_token: Optional[str] = None,
        force_full_sync: bool = False,  # Force full sync with deletion
    ) -> None:
        """Run the source connection sync workflow.

        Args:
            sync_dict: The sync configuration as dict
            sync_job_dict: The sync job as dict (optional for scheduled runs)
            sync_dag_dict: The sync DAG as dict
            collection_dict: The collection as dict
            source_connection_dict: The source connection as dict
            ctx_dict: The authentication context as dict
            access_token: Optional access token
            force_full_sync: If True, forces a full sync with orphaned entity deletion
        """
        from airweave.platform.temporal.activities import run_sync_activity

        # Create sync job if needed (for scheduled runs)
        sync_job_dict = await self._create_sync_job_if_needed(
            sync_dict, sync_job_dict, ctx_dict, force_full_sync
        )
        if sync_job_dict is None:
            return  # Exit gracefully if we couldn't create a job

        # Execute the sync activity; it is responsible for status updates when in flight
        # try:
        # Deterministic/cancellable sleep to test pre-activity cancellation
        # TODO: delete
        try:
            await workflow.execute_activity(
                run_sync_activity,
                args=[
                    sync_dict,
                    sync_job_dict,
                    sync_dag_dict,
                    collection_dict,
                    source_connection_dict,
                    ctx_dict,
                    access_token,
                    force_full_sync,
                ],
                start_to_close_timeout=timedelta(days=7),
                heartbeat_timeout=timedelta(minutes=10),
                cancellation_type=workflow.ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(minutes=5),
                    maximum_attempts=1,
                ),
            )
        except asyncio.CancelledError as e:
            # only treat true cancellations specially
            if not is_cancelled_exception(e):
                raise

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
