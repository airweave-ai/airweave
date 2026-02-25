"""CRUD operations for sync jobs."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.context import BaseContext
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.sync import Sync
from airweave.models.sync_job import SyncJob
from airweave.schemas.sync_job import SyncJobCreate, SyncJobUpdate


class CRUDSyncJob(CRUDBaseOrganization[SyncJob, SyncJobCreate, SyncJobUpdate]):
    """CRUD operations for sync jobs."""

    async def get(self, db: AsyncSession, id: UUID, ctx: BaseContext) -> SyncJob | None:
        """Get a sync job by ID."""
        stmt = (
            select(SyncJob, Sync.name.label("sync_name"))
            .join(Sync, SyncJob.sync_id == Sync.id)
            .where(SyncJob.id == id, SyncJob.organization_id == ctx.organization.id)
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
        status: Optional[list[str]] = None,
    ) -> list[SyncJob]:
        """Get all jobs for a specific sync, optionally filtered by status."""
        stmt = (
            select(SyncJob, Sync.name.label("sync_name"))
            .join(Sync, SyncJob.sync_id == Sync.id)
            .where(SyncJob.sync_id == sync_id)
        )

        # Add status filter if provided
        if status:
            # Database enum already uses uppercase values
            stmt = stmt.where(SyncJob.status.in_(status))

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

    async def get_stuck_jobs_by_status(
        self,
        db: AsyncSession,
        status: list[str],
        modified_before: Optional[datetime] = None,
        started_before: Optional[datetime] = None,
    ) -> list[SyncJob]:
        """Get sync jobs stuck in specific statuses based on timestamps.

        Args:
            db: Database session
            status: List of statuses to filter by
            modified_before: For CANCELLING/PENDING jobs - modified_at before this time
            started_before: For RUNNING jobs - started_at before this time

        Returns:
            List of stuck sync jobs
        """
        stmt = select(SyncJob).where(SyncJob.status.in_(status))

        # Apply timestamp filters based on what's provided
        if modified_before is not None:
            stmt = stmt.where(SyncJob.modified_at < modified_before)
        if started_before is not None:
            stmt = stmt.where(SyncJob.started_at < started_before)

        result = await db.execute(stmt)
        return list(result.scalars().all())


sync_job = CRUDSyncJob(SyncJob)
