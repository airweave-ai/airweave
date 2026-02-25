"""Sync job service: status updates for sync job records."""

from dataclasses import asdict
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import text

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.logging import logger
from airweave.core.shared_models import SyncJobStatus
from airweave.db.session import get_db_context
from airweave.domains.syncs.protocols import SyncJobRepositoryProtocol, SyncJobServiceProtocol
from airweave.domains.syncs.types import StatsUpdate, TimestampUpdate
from airweave.platform.sync.pipeline.entity_tracker import SyncStats


class SyncJobService(SyncJobServiceProtocol):
    """Manages sync job status updates with raw-SQL + ORM hybrid."""

    def __init__(self, sync_job_repo: SyncJobRepositoryProtocol) -> None:
        """Initialize with injected repository."""
        self._sync_job_repo = sync_job_repo

    @staticmethod
    def _build_stats_update(stats: SyncStats) -> StatsUpdate:
        """Extract stat fields from a SyncStats object."""
        return StatsUpdate(
            entities_inserted=stats.inserted,
            entities_updated=stats.updated,
            entities_deleted=stats.deleted,
            entities_kept=stats.kept,
            entities_skipped=stats.skipped,
            entities_encountered=stats.entities_encountered,
        )

    @staticmethod
    def _build_timestamp_update(
        status: SyncJobStatus,
        started_at: Optional[datetime],
        completed_at: Optional[datetime],
        failed_at: Optional[datetime],
        error: Optional[str],
    ) -> TimestampUpdate:
        """Build timestamp / error fields for the ORM update."""
        update = TimestampUpdate()
        if started_at:
            update.started_at = started_at
        if status == SyncJobStatus.COMPLETED and completed_at:
            update.completed_at = completed_at
        elif status == SyncJobStatus.FAILED:
            if failed_at:
                update.failed_at = failed_at
            if error:
                update.error = error
        return update

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

        Opens its own DB session because Temporal activity callers
        may not carry a usable session.
        """
        try:
            async with get_db_context() as db:
                db_sync_job = await self._sync_job_repo.get(db=db, id=sync_job_id, ctx=ctx)
                if not db_sync_job:
                    logger.error(f"Sync job {sync_job_id} not found")
                    return

                status_value = status.value
                logger.info(f"Updating sync job {sync_job_id} status to {status_value}")

                update_data = {}
                if stats:
                    update_data.update(asdict(self._build_stats_update(stats)))
                ts = self._build_timestamp_update(
                    status, started_at, completed_at, failed_at, error
                )
                update_data.update({k: v for k, v in asdict(ts).items() if v is not None})

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

                if update_data:
                    await self._sync_job_repo.update(
                        db=db,
                        db_obj=db_sync_job,
                        obj_in=schemas.SyncJobUpdate(**update_data),
                        ctx=ctx,
                    )

                await db.commit()
                logger.info(f"Successfully updated sync job {sync_job_id} to {status_value}")

        except Exception as e:
            logger.error(f"Failed to update sync job status: {e}")
