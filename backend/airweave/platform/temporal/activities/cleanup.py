"""Cleanup activities for orphaned Temporal workflows and schedules.

Activity classes with explicit dependency injection.
"""

from dataclasses import dataclass
from typing import Any, Dict

from temporalio import activity


@dataclass
class SelfDestructOrphanedSyncActivity:
    """Self-destruct cleanup for orphaned workflow.

    Dependencies: None (uses internal schedule service)

    Called when a workflow detects its sync/source_connection no longer exists.
    Cleans up any remaining schedules and workflows for this sync_id.
    """

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
        from airweave import schemas
        from airweave.api.context import ApiContext
        from airweave.core.logging import LoggerConfigurator

        organization = schemas.Organization(**ctx_dict["organization"])
        user = schemas.User(**ctx_dict["user"]) if ctx_dict.get("user") else None

        ctx = ApiContext(
            request_id=ctx_dict["request_id"],
            organization=organization,
            user=user,
            auth_method=ctx_dict["auth_method"],
            auth_metadata=ctx_dict.get("auth_metadata"),
            logger=LoggerConfigurator.configure_logger(
                "airweave.temporal.cleanup",
                dimensions={
                    "sync_id": sync_id,
                    "organization_id": str(organization.id),
                },
            ),
        )

        ctx.logger.info(f"🧹 Starting self-destruct cleanup for sync {sync_id}. Reason: {reason}")

        cleanup_summary = {
            "sync_id": sync_id,
            "reason": reason,
            "schedules_deleted": [],
            "workflows_cancelled": [],
            "errors": [],
        }

        # Delete all schedule types using existing schedule service logic
        from airweave.platform.temporal.schedule_service import temporal_schedule_service

        schedule_ids = [
            f"sync-{sync_id}",
            f"minute-sync-{sync_id}",
            f"daily-cleanup-{sync_id}",
        ]

        for schedule_id in schedule_ids:
            try:
                await temporal_schedule_service.delete_schedule_handle(schedule_id)
                ctx.logger.info(f"  ✓ Deleted schedule: {schedule_id}")
                cleanup_summary["schedules_deleted"].append(schedule_id)
            except Exception as e:
                ctx.logger.debug(f"  - Schedule {schedule_id} not found: {e}")

        ctx.logger.info(
            f"🧹 Self-destruct cleanup complete for sync {sync_id}. "
            f"Deleted {len(cleanup_summary['schedules_deleted'])} schedule(s)."
        )

        return cleanup_summary
