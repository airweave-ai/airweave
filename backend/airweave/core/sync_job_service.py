"""Service for managing sync job status."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from airweave import crud, schemas
from airweave.core.logging import logger
from airweave.core.shared_models import SyncJobStatus
from airweave.db.session import get_db_context


class SyncJobService:
    """Service for managing sync job status updates."""

    async def update_status(
        self,
        sync_job_id: UUID,
        status: SyncJobStatus,
        current_user: schemas.User,
        error: Optional[str] = None,
        completed_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
        stats: Optional[dict] = None,
    ) -> None:
        """Update sync job status with provided details."""
        try:
            async with get_db_context() as db:
                db_sync_job = await crud.sync_job.get(db=db, id=sync_job_id)

                if not db_sync_job:
                    logger.error(f"Sync job {sync_job_id} not found")
                    return

                update_data = {"status": status}

                if stats:
                    update_data["stats"] = stats
                    update_data["records_processed"] = stats.get("inserted", 0)
                    update_data["records_updated"] = stats.get("updated", 0)
                    update_data["records_deleted"] = stats.get("deleted", 0)

                if status == SyncJobStatus.COMPLETED and completed_at:
                    update_data["completed_at"] = completed_at
                elif status == SyncJobStatus.FAILED:
                    if failed_at:
                        update_data["failed_at"] = failed_at or datetime.now()
                    if error:
                        update_data["error"] = error

                await crud.sync_job.update(
                    db=db,
                    db_obj=db_sync_job,
                    obj_in=schemas.SyncJobUpdate(**update_data),
                    current_user=current_user,
                )
        except Exception as e:
            logger.error(f"Failed to update sync job status: {e}")


# Singleton instance
sync_job_service = SyncJobService()
