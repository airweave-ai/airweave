"""CRUD operations for sync jobs."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.crud._base import CRUDBase
from airweave.models.sync import Sync
from airweave.models.sync_job import SyncJob
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
        status: Optional[list[str]] = None,
    ) -> list[SyncJob]:
        """Get all sync jobs across all syncs, optionally filtered by status."""
        stmt = select(SyncJob, Sync.name.label("sync_name")).join(Sync, SyncJob.sync_id == Sync.id)

        # Add status filter if provided
        if status:
            stmt = stmt.where(SyncJob.status.in_(status))

        stmt = stmt.order_by(SyncJob.created_at.desc()).offset(skip).limit(limit)

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


sync_job = CRUDSyncJob(SyncJob)
