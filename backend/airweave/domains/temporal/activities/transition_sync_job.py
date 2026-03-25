"""Transition sync job activity — thin Temporal wrapper over SyncJobStateMachine.

Called by the workflow for COMPLETED, FAILED, and CANCELLED transitions.
Deserializes Temporal payloads and delegates to the state machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import UUID

from temporalio import activity

from airweave.core.shared_models import SyncJobStatus
from airweave.domains.sync_pipeline.pipeline.entity_tracker import SyncStats
from airweave.domains.syncs.jobs.protocols import SyncJobStateMachineProtocol
from airweave.domains.syncs.jobs.types import LifecycleData
from airweave.domains.temporal.activities.context import build_activity_context

_STATUS_MAP: dict[str, SyncJobStatus] = {
    "completed": SyncJobStatus.COMPLETED,
    "failed": SyncJobStatus.FAILED,
    "cancelled": SyncJobStatus.CANCELLED,
}


@dataclass
class TransitionSyncJobActivity:
    """Temporal activity: deserialize payloads and delegate to SyncJobStateMachine.

    Dependencies:
        state_machine: Validates, writes DB, publishes lifecycle events.
    """

    state_machine: SyncJobStateMachineProtocol

    @activity.defn(name="transition_sync_job_activity")
    async def run(
        self,
        transition: str,
        sync_job_id: str,
        ctx_dict: Dict[str, Any],
        lifecycle_data: Dict[str, Any],
        error: Optional[str] = None,
        stats_dict: Optional[Dict[str, Any]] = None,
        timestamp_iso: Optional[str] = None,
    ) -> None:
        """Execute a terminal state transition via the state machine.

        Args:
            transition: One of "completed", "failed", "cancelled".
            sync_job_id: The sync job UUID as a string.
            ctx_dict: Serialized context dict (contains organization).
            lifecycle_data: Fields for building LifecycleData.
            error: Error message (for failed transitions).
            stats_dict: Serialized SyncStats fields.
            timestamp_iso: Ignored (timestamps are derived by the state machine).
        """
        target = _STATUS_MAP.get(transition)
        if target is None:
            raise ValueError(f"Unknown transition: {transition!r}")

        ctx = await build_activity_context(ctx_dict, sync_job_id=sync_job_id)

        stats = SyncStats(**stats_dict) if stats_dict else None

        _UUID_FIELDS = {
            "organization_id",
            "sync_id",
            "sync_job_id",
            "collection_id",
            "source_connection_id",
        }
        ld_kwargs: Dict[str, Any] = {
            k: UUID(v) if k in _UUID_FIELDS and isinstance(v, str) else v
            for k, v in lifecycle_data.items()
        }
        ld = LifecycleData(**ld_kwargs)  # type: ignore[arg-type]

        ctx.logger.info(f"Transitioning sync job {sync_job_id} to {transition}")

        await self.state_machine.transition(
            sync_job_id=UUID(sync_job_id),
            target=target,
            ctx=ctx,
            lifecycle_data=ld,
            error=error,
            stats=stats,
        )
