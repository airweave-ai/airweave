"""Temporal activity for self-destructing orphaned sync workflows."""

from dataclasses import dataclass
from typing import Any, Dict

from temporalio import activity

from airweave import schemas
from airweave.core.context import BaseContext
from airweave.domains.temporal.protocols import TemporalScheduleServiceProtocol


@dataclass
class SelfDestructOrphanedSyncActivity:
    """Self-destruct cleanup for orphaned workflow.

    Called when a workflow detects its sync/source_connection no longer exists.
    """

    temporal_schedule_service: TemporalScheduleServiceProtocol

    @activity.defn(name="self_destruct_orphaned_sync_activity")
    async def run(
        self,
        sync_id: str,
        ctx_dict: Dict[str, Any],
        reason: str = "Resource not found",
    ) -> Dict[str, Any]:
        """Delete all Temporal schedules for the orphaned sync."""
        organization = schemas.Organization(**ctx_dict["organization"])
        ctx = BaseContext(organization=organization)
        ctx.logger = ctx.logger.with_context(sync_id=sync_id)

        ctx.logger.info(f"Starting self-destruct cleanup for sync {sync_id}. Reason: {reason}")

        cleanup_summary: Dict[str, Any] = {
            "sync_id": sync_id,
            "reason": reason,
            "schedules_deleted": [],
            "workflows_cancelled": [],
            "errors": [],
        }

        schedule_ids = [
            f"sync-{sync_id}",
            f"minute-sync-{sync_id}",
            f"daily-cleanup-{sync_id}",
        ]

        for schedule_id in schedule_ids:
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
