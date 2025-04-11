"""CRUD operations for sync jobs."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.logging import logger
from airweave.core.shared_models import SyncJobStatus
from airweave.crud._base import CRUDBase
from airweave.db.session import get_db_context
from airweave.models.sync import Sync
from airweave.models.sync_job import SyncJob
from airweave.platform.sync.pubsub import SyncProgress
from airweave.schemas.sync_job import SyncJobCreate, SyncJobUpdate


class CRUDSyncJob(CRUDBase[SyncJob, SyncJobCreate, SyncJobUpdate]):
    """CRUD operations for sync jobs."""

    async def get(self, db: AsyncSession, id: UUID, current_user=None) -> SyncJob | None:
        """Get a sync job by ID."""
        stmt = (
            select(SyncJob, Sync.name.label("sync_name"))
            .join(Sync, SyncJob.sync_id == Sync.id)
            .where(SyncJob.id == id)
        )
        result = await db.execute(stmt)
        row = result.first()
        if not row:
            return None

        job, sync_name = row
        # Add the sync name to the job object
        job.sync_name = sync_name
        return job

    async def get_all_by_sync_id(
        self,
        db: AsyncSession,
        sync_id: UUID,
    ) -> list[SyncJob]:
        """Get all jobs for a specific sync."""
        stmt = (
            select(SyncJob, Sync.name.label("sync_name"))
            .join(Sync, SyncJob.sync_id == Sync.id)
            .where(SyncJob.sync_id == sync_id)
        )
        result = await db.execute(stmt)
        jobs = []
        for job, sync_name in result:
            job.sync_name = sync_name
            jobs.append(job)
        return jobs

    async def get_all_jobs(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        current_user=None,
    ) -> list[SyncJob]:
        """Get all sync jobs across all syncs."""
        stmt = (
            select(SyncJob, Sync.name.label("sync_name"))
            .join(Sync, SyncJob.sync_id == Sync.id)
            .order_by(SyncJob.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        jobs = []
        for job, sync_name in result:
            job.sync_name = sync_name
            jobs.append(job)
        return jobs

    async def get_latest_by_sync_id(
        self,
        db: AsyncSession,
        sync_id: UUID,
    ) -> SyncJob | None:
        """Get the most recent job for a specific sync."""
        stmt = (
            select(SyncJob, Sync.name.label("sync_name"))
            .join(Sync, SyncJob.sync_id == Sync.id)
            .where(SyncJob.sync_id == sync_id)
            .order_by(SyncJob.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        row = result.first()
        if not row:
            return None

        job, sync_name = row
        # Add the sync name to the job object
        job.sync_name = sync_name
        return job

    async def update_status(
        self,
        job_id: UUID,
        status: SyncJobStatus,
        progress: SyncProgress,
        current_user,
        error: Optional[str] = None,
        completed_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
    ) -> None:
        """Update sync job status with progress statistics.

        Args:
            job_id: The sync job ID
            status: The new status to set
            progress: Progress tracker with statistics
            current_user: The user performing the update
            error: Optional error message for failed jobs
            completed_at: Optional timestamp for completed jobs
            failed_at: Optional timestamp for failed jobs
        """
        async with get_db_context() as db:
            try:
                # Get the database model for the sync job
                stmt = select(SyncJob).where(SyncJob.id == job_id)
                result = await db.execute(stmt)
                db_sync_job = result.scalar_one_or_none()

                if not db_sync_job:
                    logger.error(f"Sync job with ID {job_id} not found in database")
                    return

                # Prepare update data with CORRECT field names from SyncJobUpdate schema
                update_data = SyncJobUpdate(
                    status=status,
                    records_created=progress.stats.inserted,
                    records_updated=progress.stats.updated,
                    records_deleted=progress.stats.deleted,
                    error=error,
                    completed_at=completed_at,
                    failed_at=failed_at,
                )

                # Update the sync job
                await self.update(
                    db=db,
                    db_obj=db_sync_job,
                    obj_in=update_data,
                    current_user=current_user,
                )
            except Exception as e:
                # Log but don't re-raise to avoid masking the original error
                logger.error(f"Failed to update sync job status: {e}")


sync_job = CRUDSyncJob(SyncJob)
