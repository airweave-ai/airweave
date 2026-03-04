"""Cleanup activities for orphaned Temporal workflows and schedules.

Activity classes with explicit dependency injection.
"""

from dataclasses import dataclass
from typing import Any, Dict, List

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
        from airweave.core.context import BaseContext

        organization = schemas.Organization(**ctx_dict["organization"])

        ctx = BaseContext(organization=organization)
        ctx.logger = ctx.logger.with_context(sync_id=sync_id)

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


@dataclass
class CleanupSyncDataActivity:
    """Clean up external data (Vespa, ARF, schedules) for deleted syncs.

    Dependencies: None (uses internal services)

    This activity runs asynchronously after a source connection or collection
    has been deleted from the database. It handles the slow, potentially
    long-running cleanup of destination data (Vespa can take minutes),
    Temporal schedules, and ARF storage.

    Accepts only primitive IDs -- no full schemas or dicts -- so the Temporal
    payload stays small and the activity is self-contained.

    Since the DB records are already gone by the time this runs, failure is
    non-critical -- the data in Vespa is just orphaned (unsearchable since
    the collection metadata no longer exists).
    """

    @activity.defn(name="cleanup_sync_data_activity")
    async def run(
        self,
        sync_ids: List[str],
        collection_id: str,
        organization_id: str,
    ) -> Dict[str, Any]:
        """Clean up external data for one or more syncs.

        Args:
            sync_ids: List of sync ID strings to clean up.
            collection_id: Collection UUID string (for Vespa scoped deletion).
            organization_id: Organization UUID string (for Vespa client init).

        Returns:
            Summary of cleanup actions and any errors.
        """
        from uuid import UUID

        from airweave.core.logging import LoggerConfigurator
        from airweave.platform.destinations.vespa.destination import VespaDestination
        from airweave.platform.sync.arf import arf_service
        from airweave.platform.temporal.schedule_service import temporal_schedule_service

        logger = LoggerConfigurator.configure_logger(
            "airweave.temporal.cleanup_sync_data",
            dimensions={
                "collection_id": collection_id,
                "sync_count": str(len(sync_ids)),
            },
        )

        col_uuid = UUID(collection_id)
        org_uuid = UUID(organization_id)

        summary: Dict[str, Any] = {
            "syncs_processed": 0,
            "destinations_cleaned": 0,
            "schedules_deleted": 0,
            "arf_deleted": 0,
            "errors": [],
        }

        # Build Vespa destination once (only needs collection_id + organization_id)
        vespa: VespaDestination | None = None
        try:
            vespa = await VespaDestination.create(
                collection_id=col_uuid,
                organization_id=org_uuid,
                logger=logger,
            )
        except Exception as e:
            error_msg = f"Failed to create Vespa destination for cleanup: {e}"
            logger.error(error_msg)
            summary["errors"].append(error_msg)

        for sync_id_str in sync_ids:
            sync_id = UUID(sync_id_str)
            logger.info(f"Cleaning up external data for sync {sync_id}")

            # 1. Temporal schedules (fast)
            for prefix in ("sync", "minute-sync", "daily-cleanup"):
                schedule_id = f"{prefix}-{sync_id}"
                try:
                    await temporal_schedule_service.delete_schedule_handle(schedule_id)
                    summary["schedules_deleted"] += 1
                except Exception as e:
                    logger.debug(f"Schedule {schedule_id} not deleted: {e}")

            # 2. Vespa data (potentially slow)
            if vespa:
                try:
                    await vespa.delete_by_sync_id(sync_id)
                    summary["destinations_cleaned"] += 1
                    logger.info(f"Deleted Vespa data for sync {sync_id}")
                except Exception as e:
                    error_msg = f"Failed to delete Vespa data for sync {sync_id}: {e}"
                    logger.error(error_msg)
                    summary["errors"].append(error_msg)

            # 3. ARF storage
            try:
                if await arf_service.sync_exists(sync_id_str):
                    deleted = await arf_service.delete_sync(sync_id_str)
                    if deleted:
                        summary["arf_deleted"] += 1
                        logger.debug(f"Deleted ARF store for sync {sync_id}")
            except Exception as e:
                error_msg = f"Failed to cleanup ARF for sync {sync_id}: {e}"
                logger.warning(error_msg)
                summary["errors"].append(error_msg)

            summary["syncs_processed"] += 1

        logger.info(
            f"Cleanup complete: {summary['syncs_processed']} sync(s), "
            f"{summary['destinations_cleaned']} destination(s), "
            f"{summary['schedules_deleted']} schedule(s), "
            f"{summary['arf_deleted']} ARF store(s), "
            f"{len(summary['errors'])} error(s)"
        )

        return summary
