"""Temporal workflow for running a source connection sync."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, Dict, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from airweave.platform.temporal.activities import (
        create_sync_job_activity,
        mark_sync_job_cancelled_activity,
        run_sync_activity,
        self_destruct_orphaned_sync_activity,
    )

# ---------------------------------------------------------------------------
# Named constants — timeouts and retry policies
# ---------------------------------------------------------------------------

FAIL_FAST = RetryPolicy(maximum_attempts=1)

_CREATE_JOB_TIMEOUT = timedelta(seconds=30)
_CREATE_JOB_FORCED_TIMEOUT = timedelta(hours=1, minutes=5)
_CREATE_JOB_FORCED_HEARTBEAT = timedelta(minutes=1)

_SYNC_TIMEOUT = timedelta(days=7)
_HEARTBEAT_TIMEOUT = timedelta(minutes=15)
_HEARTBEAT_TIMEOUT_LOCAL = timedelta(hours=1)

_SELF_DESTRUCT_TIMEOUT = timedelta(minutes=5)
_SELF_DESTRUCT_RETRIES = RetryPolicy(maximum_attempts=3)

_MARK_CANCELLED_TIMEOUT = timedelta(seconds=30)


@workflow.defn
class RunSourceConnectionWorkflow:
    """Workflow for running a source connection sync.

    Phases:
        1. ensure_sync_job — create a sync job for scheduled runs, or validate the provided one
        2. detect orphan — if the sync no longer exists, self-destruct its schedules
        3. execute — run the sync activity with heartbeat monitoring
        4. handle failure — route errors to orphan cleanup, cancellation marking, or re-raise
    """

    @workflow.run
    async def run(
        self,
        sync_dict: Dict[str, Any],
        sync_job_dict: Optional[Dict[str, Any]],
        collection_dict: Dict[str, Any],
        connection_dict: Dict[str, Any],
        ctx_dict: Dict[str, Any],
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
    ) -> None:
        """Run the source connection sync workflow."""
        sync_id: str = sync_dict["id"]

        # Phase 1: ensure we have a sync job
        sync_job_dict = await self._ensure_sync_job(
            sync_id, sync_job_dict, ctx_dict, force_full_sync
        )
        if sync_job_dict is None:
            return

        # Phase 2: handle orphaned sync (pre-execution)
        if sync_job_dict.get("_orphaned"):
            reason = sync_job_dict.get("reason", "Unknown")
            workflow.logger.info(
                f"Sync {sync_id} is orphaned. Reason: {reason}. Initiating self-destruct cleanup..."
            )
            await self._self_destruct(sync_id, ctx_dict, reason)
            return

        # Phase 3: execute sync + handle failures
        await self._execute_sync(
            sync_dict,
            sync_job_dict,
            collection_dict,
            connection_dict,
            ctx_dict,
            access_token,
            force_full_sync,
        )

    # ------------------------------------------------------------------
    # Phase 1: ensure sync job
    # ------------------------------------------------------------------

    async def _ensure_sync_job(
        self,
        sync_id: str,
        sync_job_dict: Optional[Dict[str, Any]],
        ctx_dict: Dict[str, Any],
        force_full_sync: bool,
    ) -> Optional[Dict[str, Any]]:
        """Create a sync job for scheduled runs, or return the existing one.

        Returns None when the run should be skipped.
        """
        if sync_job_dict is not None:
            return sync_job_dict

        timeout = _CREATE_JOB_FORCED_TIMEOUT if force_full_sync else _CREATE_JOB_TIMEOUT
        heartbeat = _CREATE_JOB_FORCED_HEARTBEAT if force_full_sync else None

        try:
            sync_job_dict = await workflow.execute_activity(
                create_sync_job_activity,
                args=[sync_id, ctx_dict, force_full_sync],
                start_to_close_timeout=timeout,
                heartbeat_timeout=heartbeat,
                retry_policy=FAIL_FAST,
            )
        except Exception as e:
            workflow.logger.warning(f"Skipping scheduled run for sync {sync_id}: {e}")
            return None

        if sync_job_dict and sync_job_dict.get("_skipped"):
            workflow.logger.info(
                f"Skipping scheduled run for sync {sync_id}: "
                f"{sync_job_dict.get('reason', 'already running')}"
            )
            return None

        return sync_job_dict

    # ------------------------------------------------------------------
    # Phase 2: self-destruct orphaned sync
    # ------------------------------------------------------------------

    async def _self_destruct(
        self,
        sync_id: str,
        ctx_dict: Dict[str, Any],
        reason: str,
    ) -> None:
        """Clean up all Temporal schedules for an orphaned sync."""
        try:
            await workflow.execute_activity(
                self_destruct_orphaned_sync_activity,
                args=[sync_id, ctx_dict, reason],
                start_to_close_timeout=_SELF_DESTRUCT_TIMEOUT,
                retry_policy=_SELF_DESTRUCT_RETRIES,
            )
            workflow.logger.info(f"Self-destruct cleanup complete for sync {sync_id}")
        except Exception as cleanup_error:
            workflow.logger.warning(
                f"Self-destruct cleanup encountered an error: {cleanup_error}. "
                f"Continuing graceful exit."
            )

    # ------------------------------------------------------------------
    # Phase 3: execute sync
    # ------------------------------------------------------------------

    async def _execute_sync(
        self,
        sync_dict: Dict[str, Any],
        sync_job_dict: Dict[str, Any],
        collection_dict: Dict[str, Any],
        connection_dict: Dict[str, Any],
        ctx_dict: Dict[str, Any],
        access_token: Optional[str],
        force_full_sync: bool,
    ) -> None:
        """Run the sync activity and route any failures."""
        local_development = ctx_dict.get("local_development", False)
        heartbeat_timeout = _HEARTBEAT_TIMEOUT_LOCAL if local_development else _HEARTBEAT_TIMEOUT

        try:
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
                start_to_close_timeout=_SYNC_TIMEOUT,
                heartbeat_timeout=heartbeat_timeout,
                cancellation_type=workflow.ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
                retry_policy=FAIL_FAST,
            )
        except Exception as e:
            await self._handle_sync_failure(e, sync_dict, sync_job_dict, ctx_dict)

    # ------------------------------------------------------------------
    # Phase 4: failure routing
    # ------------------------------------------------------------------

    async def _handle_sync_failure(
        self,
        error: BaseException,
        sync_dict: Dict[str, Any],
        sync_job_dict: Dict[str, Any],
        ctx_dict: Dict[str, Any],
    ) -> None:
        """Route sync failures: orphan → self-destruct, cancel → mark, else → re-raise."""
        sync_id = sync_dict["id"]

        # Build a combined error string to check for ORPHANED_SYNC marker
        error_str = str(error)
        if hasattr(error, "__cause__") and error.__cause__:
            error_str += f" {error.__cause__}"

        if "ORPHANED_SYNC" in error_str:
            workflow.logger.info(
                f"Sync {sync_id} became orphaned during execution. "
                f"Initiating self-destruct cleanup..."
            )
            await self._self_destruct(
                sync_id, ctx_dict, "Source connection deleted during sync execution"
            )
            return

        if isinstance(error, asyncio.CancelledError):
            reason = f"{type(error).__name__}: {error}"
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
                        start_to_close_timeout=_MARK_CANCELLED_TIMEOUT,
                        cancellation_type=workflow.ActivityCancellationType.ABANDON,
                    )
                )
            finally:
                raise

        raise error
