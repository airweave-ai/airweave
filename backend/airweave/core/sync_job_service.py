"""Service for managing sync job status."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.logging import logger
from airweave.core.shared_models import SyncJobStatus
from airweave.db.session import get_db_context
from airweave.platform.sync.pipeline.entity_tracker import SyncStats


class SyncJobService:
    """Service for managing sync job status updates."""

    def _build_stats_update_data(self, stats: SyncStats) -> Dict[str, Any]:
        """Build update data from stats."""
        update_data = {
            "entities_inserted": stats.inserted,
            "entities_updated": stats.updated,
            "entities_deleted": stats.deleted,
            "entities_kept": stats.kept,
            "entities_skipped": stats.skipped,
        }

        update_data["entities_encountered"] = stats.entities_encountered

        return update_data

    def _build_timestamp_update_data(
        self,
        status: SyncJobStatus,
        started_at: Optional[datetime],
        completed_at: Optional[datetime],
        failed_at: Optional[datetime],
        error: Optional[str],
    ) -> Dict[str, Any]:
        """Build timestamp and error update data."""
        update_data = {}

        if started_at:
            update_data["started_at"] = started_at

        if status == SyncJobStatus.COMPLETED and completed_at:
            update_data["completed_at"] = completed_at
        elif status == SyncJobStatus.FAILED:
            if failed_at:
                update_data["failed_at"] = failed_at or utc_now_naive()
            if error:
                update_data["error"] = error

        return update_data

    async def _update_status_in_database(self, db, sync_job_id: UUID, status_value: str) -> None:
        """Update status field using raw SQL."""
        from sqlalchemy import text

        # Update status with string value directly
        await db.execute(
            text(
                "UPDATE sync_job SET status = :status, "
                "modified_at = :modified_at WHERE id = :sync_job_id"
            ),
            {
                "status": status_value,
                "modified_at": utc_now_naive(),
                "sync_job_id": sync_job_id,
            },
        )

    async def update_status(
        self,
        sync_job_id: UUID,
        status: SyncJobStatus,
        ctx: ApiContext,
        stats: Optional[SyncStats] = None,
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
    ) -> None:
        """Update sync job status with provided details.

        Args:
            sync_job_id: ID of the sync job
            status: New status
            ctx: API context
            stats: Optional stats object (SyncProgressUpdate or SyncStats)
            error: Optional error message
            started_at: Optional start time
            completed_at: Optional completion time
            failed_at: Optional failure time
        """
        try:
            async with get_db_context() as db:
                db_sync_job = await crud.sync_job.get(db=db, id=sync_job_id, ctx=ctx)

                if not db_sync_job:
                    logger.error(f"Sync job {sync_job_id} not found")
                    return

                # Use the enum value directly (it's already a string)
                status_value = status.value
                logger.info(f"Updating sync job {sync_job_id} status to {status_value}")

                update_data = {"status": status}

                if stats:
                    stats_data = self._build_stats_update_data(stats)
                    update_data.update(stats_data)

                timestamp_data = self._build_timestamp_update_data(
                    status, started_at, completed_at, failed_at, error
                )
                update_data.update(timestamp_data)

                # Update status using raw SQL
                await self._update_status_in_database(db, sync_job_id, status_value)

                # Update other fields using the normal ORM
                # (excluding status which we already updated)
                update_data.pop("status")
                if update_data:
                    await crud.sync_job.update(
                        db=db,
                        db_obj=db_sync_job,
                        obj_in=schemas.SyncJobUpdate(**update_data),
                        ctx=ctx,
                    )

                await db.commit()
                logger.info(f"Successfully updated sync job {sync_job_id} status to {status_value}")

        except Exception as e:
            logger.error(f"Failed to update sync job status: {e}")
            return


# Singleton instance
sync_job_service = SyncJobService()
