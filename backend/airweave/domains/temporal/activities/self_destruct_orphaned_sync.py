"""Self-destruct orphaned sync activity — cleans up schedules for deleted syncs."""

from dataclasses import dataclass
from typing import Any, Dict

from temporalio import activity

from airweave.domains.temporal import schedule_ids
from airweave.domains.temporal.activities.context import build_activity_context
from airweave.domains.temporal.protocols import TemporalScheduleServiceProtocol


@dataclass
class SelfDestructOrphanedSyncActivity:
    """Self-destruct cleanup for orphaned workflow.

    Dependencies:
        temporal_schedule_service: Delete orphaned Temporal schedules

    Called when a workflow detects its sync/source_connection no longer exists.
    Cleans up any remaining schedules and workflows for this sync_id.
    """

    temporal_schedule_service: TemporalScheduleServiceProtocol

    @activity.defn(name="self_destruct_orphaned_sync_activity")
    async def run(
        self,
        sync_id: str,
        ctx_dict: Dict[str, Any],
        reason: str = "Resource not found",
    ) -> Dict[str, Any]:
        """Self-destruct cleanup for orphaned workflow.

        Args:
            sync_id: The sync ID to clean up
            ctx_dict: The API context as dict
            reason: Reason for cleanup (for logging)

        Returns:
            Summary of cleanup actions performed
        """
        ctx = build_activity_context(ctx_dict, sync_id=sync_id)

        ctx.logger.info(f"Starting self-destruct cleanup for sync {sync_id}. Reason: {reason}")

        cleanup_summary: Dict[str, Any] = {
            "sync_id": sync_id,
            "reason": reason,
            "schedules_deleted": [],
            "workflows_cancelled": [],
            "errors": [],
        }

        all_sids = schedule_ids.all_schedule_ids(sync_id)

        for schedule_id in all_sids:
            try:
                await self.temporal_schedule_service.delete_schedule_handle(schedule_id)
                ctx.logger.info(f"  Deleted schedule: {schedule_id}")
                cleanup_summary["schedules_deleted"].append(schedule_id)
            except Exception as e:
                ctx.logger.debug(f"  Schedule {schedule_id} not found: {e}")

        ctx.logger.info(
            f"Self-destruct cleanup complete for sync {sync_id}. "
            f"Deleted {len(cleanup_summary['schedules_deleted'])} schedule(s)."
        )

        return cleanup_summary
