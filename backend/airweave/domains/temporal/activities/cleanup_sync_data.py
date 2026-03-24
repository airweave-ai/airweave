"""Cleanup sync data activity — removes external data (Vespa, ARF, schedules) for deleted syncs."""

from dataclasses import dataclass
from typing import Any, Dict, List
from uuid import UUID

from temporalio import activity

from airweave.core.logging import LoggerConfigurator
from airweave.domains.arf.protocols import ArfServiceProtocol
from airweave.domains.temporal import schedule_ids
from airweave.domains.temporal.protocols import TemporalScheduleServiceProtocol
from airweave.platform.destinations.vespa.destination import VespaDestination


@dataclass
class CleanupSyncDataActivity:
    """Clean up external data (Vespa, ARF, schedules) for deleted syncs.

    Dependencies:
        temporal_schedule_service: Delete orphaned Temporal schedules
        arf_service: Delete ARF stores for cleaned-up syncs

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

    temporal_schedule_service: TemporalScheduleServiceProtocol
    arf_service: ArfServiceProtocol

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

            for sid in schedule_ids.all_schedule_ids(sync_id):
                try:
                    await self.temporal_schedule_service.delete_schedule_handle(sid)
                    summary["schedules_deleted"] += 1
                except Exception as e:
                    logger.debug(f"Schedule {sid} not deleted: {e}")

            if vespa:
                try:
                    await vespa.delete_by_sync_id(sync_id)
                    summary["destinations_cleaned"] += 1
                    logger.info(f"Deleted Vespa data for sync {sync_id}")
                except Exception as e:
                    error_msg = f"Failed to delete Vespa data for sync {sync_id}: {e}"
                    logger.error(error_msg)
                    summary["errors"].append(error_msg)

            try:
                if await self.arf_service.sync_exists(sync_id_str):
                    deleted = await self.arf_service.delete_sync(sync_id_str)
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
