"""Run source connection workflow — the sync state machine.

Owns terminal state transitions (COMPLETED, FAILED, CANCELLED) via
TransitionSyncJobActivity. RUNNING is published by the orchestrator
because only it knows when sync work actually begins.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, Dict, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import (
    ActivityError,
    ApplicationError,
    is_cancelled_exception,
)

with workflow.unsafe.imports_passed_through():
    from airweave.domains.temporal.activities import (
        create_sync_job_activity,
        run_sync_activity,
        self_destruct_orphaned_sync_activity,
        transition_sync_job_activity,
    )
    from airweave.domains.temporal.activity_results import CreateSyncJobResult
    from airweave.domains.temporal.exceptions import ORPHANED_SYNC_ERROR_TYPE

# ---------------------------------------------------------------------------
# Execution policies
# ---------------------------------------------------------------------------

_CREATE_JOB_TIMEOUT = timedelta(seconds=30)
_CREATE_JOB_FORCE_TIMEOUT = timedelta(hours=1, minutes=5)
_CREATE_JOB_HEARTBEAT_TIMEOUT = timedelta(minutes=1)

_SYNC_TIMEOUT = timedelta(days=7)
_HEARTBEAT_TIMEOUT = timedelta(minutes=15)
_HEARTBEAT_TIMEOUT_LOCAL = timedelta(hours=1)

_SELF_DESTRUCT_TIMEOUT = timedelta(minutes=5)
_SELF_DESTRUCT_RETRY = RetryPolicy(maximum_attempts=3)

_TRANSITION_TIMEOUT = timedelta(seconds=30)
_TRANSITION_RETRY = RetryPolicy(maximum_attempts=3)

_NO_RETRY = RetryPolicy(maximum_attempts=1)


@workflow.defn
class RunSourceConnectionWorkflow:
    """Workflow for running a source connection sync.

    State machine:
        1. _ensure_sync_job  — create or reuse a sync job (PENDING)
        2. _execute_sync     — run the sync activity (RUNNING published by orchestrator)
        3. _transition       — COMPLETED | FAILED | CANCELLED (via TransitionSyncJobActivity)
        4. _self_destruct    — clean up orphaned syncs
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
        sync_job_dict = await self._ensure_sync_job(
            sync_dict, sync_job_dict, ctx_dict, force_full_sync
        )
        if sync_job_dict is None:
            return

        lifecycle = self._lifecycle_data(
            sync_dict, sync_job_dict, collection_dict, connection_dict, ctx_dict
        )

        try:
            await self._execute_sync(
                sync_dict,
                sync_job_dict,
                collection_dict,
                connection_dict,
                ctx_dict,
                access_token,
                force_full_sync,
            )
        except BaseException as e:
            if is_cancelled_exception(e):
                await self._transition("cancelled", sync_job_dict, ctx_dict, lifecycle, shield=True)
                raise
            if self._is_orphaned_sync_error(e):
                reason = self._extract_orphaned_reason(e)
                await self._self_destruct(sync_dict, ctx_dict, reason)
                return
            await self._transition("failed", sync_job_dict, ctx_dict, lifecycle, error=str(e))
            raise

        await self._transition("completed", sync_job_dict, ctx_dict, lifecycle)

    # ------------------------------------------------------------------
    # Phase 1: Ensure sync job
    # ------------------------------------------------------------------

    async def _ensure_sync_job(
        self,
        sync_dict: Dict[str, Any],
        sync_job_dict: Optional[Dict[str, Any]],
        ctx_dict: Dict[str, Any],
        force_full_sync: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Create sync job for scheduled runs or return existing one.

        Returns the sync_job_dict to use, or None to skip the workflow.
        Triggers self-destruct and returns None for orphaned syncs.
        """
        sync_id = sync_dict.get("id")

        if sync_job_dict is not None:
            return sync_job_dict

        try:
            timeout = _CREATE_JOB_FORCE_TIMEOUT if force_full_sync else _CREATE_JOB_TIMEOUT
            heartbeat = _CREATE_JOB_HEARTBEAT_TIMEOUT if force_full_sync else None

            result: CreateSyncJobResult = await workflow.execute_activity(
                create_sync_job_activity,
                args=[sync_id, ctx_dict, force_full_sync],
                start_to_close_timeout=timeout,
                heartbeat_timeout=heartbeat,
                retry_policy=_NO_RETRY,
            )
        except Exception as e:
            workflow.logger.warning(f"Skipping scheduled run for sync {sync_id}: {e}")
            return None

        if result.orphaned:
            await self._self_destruct(sync_dict, ctx_dict, result.reason)
            return None

        if result.skipped:
            workflow.logger.info(
                f"Skipping scheduled run for sync {sync_id}: {result.reason or 'already running'}"
            )
            return None

        return result.sync_job_dict

    # ------------------------------------------------------------------
    # Phase 2: Execute sync
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
        """Run the sync activity with appropriate timeouts."""
        local_development = ctx_dict.get("local_development", False)
        heartbeat_timeout = _HEARTBEAT_TIMEOUT_LOCAL if local_development else _HEARTBEAT_TIMEOUT

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
            retry_policy=_NO_RETRY,
        )

    # ------------------------------------------------------------------
    # Phase 3: State transitions
    # ------------------------------------------------------------------

    async def _transition(
        self,
        transition: str,
        sync_job_dict: Dict[str, Any],
        ctx_dict: Dict[str, Any],
        lifecycle_data: Dict[str, Any],
        *,
        error: Optional[str] = None,
        shield: bool = False,
    ) -> None:
        """Call TransitionSyncJobActivity for a terminal state change."""
        timestamp = workflow.now().replace(tzinfo=None).isoformat()
        coro = workflow.execute_activity(
            transition_sync_job_activity,
            args=[
                transition,
                str(sync_job_dict["id"]),
                ctx_dict,
                lifecycle_data,
                error,
                None,
                timestamp,
            ],
            start_to_close_timeout=_TRANSITION_TIMEOUT,
            retry_policy=_TRANSITION_RETRY,
            cancellation_type=(
                workflow.ActivityCancellationType.ABANDON
                if shield
                else workflow.ActivityCancellationType.TRY_CANCEL
            ),
        )
        try:
            await (asyncio.shield(coro) if shield else coro)
        except Exception:
            workflow.logger.warning(
                f"Failed to transition sync job {sync_job_dict.get('id')} to {transition}"
            )

    # ------------------------------------------------------------------
    # Self-destruct orphaned sync
    # ------------------------------------------------------------------

    async def _self_destruct(
        self,
        sync_dict: Dict[str, Any],
        ctx_dict: Dict[str, Any],
        reason: str = "Source connection not found",
    ) -> None:
        """Clean up schedules for an orphaned sync and exit gracefully."""
        sync_id = sync_dict["id"]
        workflow.logger.info(
            f"Sync {sync_id} is orphaned ({reason}). Initiating self-destruct cleanup."
        )

        try:
            await workflow.execute_activity(
                self_destruct_orphaned_sync_activity,
                args=[sync_id, ctx_dict, reason],
                start_to_close_timeout=_SELF_DESTRUCT_TIMEOUT,
                retry_policy=_SELF_DESTRUCT_RETRY,
            )
            workflow.logger.info(f"Self-destruct cleanup complete for sync {sync_id}")
        except Exception as cleanup_error:
            workflow.logger.warning(
                f"Self-destruct cleanup error for sync {sync_id}: {cleanup_error}"
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _lifecycle_data(
        sync_dict: Dict[str, Any],
        sync_job_dict: Dict[str, Any],
        collection_dict: Dict[str, Any],
        connection_dict: Dict[str, Any],
        ctx_dict: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Extract lifecycle event fields from input dicts (built once, reused)."""
        return {
            "organization_id": ctx_dict["organization"]["id"],
            "sync_id": sync_dict["id"],
            "sync_job_id": sync_job_dict["id"],
            "collection_id": collection_dict["id"],
            "source_connection_id": sync_dict.get("source_connection_id", ""),
            "source_type": connection_dict.get("short_name", ""),
            "collection_name": collection_dict.get("name", ""),
            "collection_readable_id": collection_dict.get("readable_id", ""),
        }

    @staticmethod
    def _is_orphaned_sync_error(error: BaseException) -> bool:
        """Check whether a Temporal ActivityError wraps an OrphanedSyncError.

        The activity converts OrphanedSyncError to an explicit ApplicationError
        with type=ORPHANED_SYNC_ERROR_TYPE, so we match on that string.
        """
        if isinstance(error, ActivityError) and isinstance(error.cause, ApplicationError):
            return error.cause.type == ORPHANED_SYNC_ERROR_TYPE
        return False

    @staticmethod
    def _extract_orphaned_reason(error: BaseException) -> str:
        """Extract the reason string from an orphaned sync ActivityError.

        The activity stores (sync_id, reason) in ApplicationError.details.
        Falls back to the error message if details are unavailable.
        """
        if isinstance(error, ActivityError) and isinstance(error.cause, ApplicationError):
            details = error.cause.details
            if len(details) >= 2:
                return str(details[1])
        return str(error)
