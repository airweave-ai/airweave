"""Sync record service: create and trigger operations for Sync/SyncJob records."""

from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.shared_models import SyncJobStatus, SyncStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.syncs.protocols import (
    SyncJobRepositoryProtocol,
    SyncRecordServiceProtocol,
    SyncRepositoryProtocol,
)
from airweave.schemas.sync import SyncCreate
from airweave.schemas.sync_job import SyncJobCreate


class SyncRecordService(SyncRecordServiceProtocol):
    """Create syncs, trigger sync runs, and list sync jobs via injected repositories."""

    def __init__(
        self,
        sync_repo: SyncRepositoryProtocol,
        sync_job_repo: SyncJobRepositoryProtocol,
    ) -> None:
        """Initialize with injected repositories."""
        self._sync_repo = sync_repo
        self._sync_job_repo = sync_job_repo

    async def create_sync(
        self,
        db: AsyncSession,
        *,
        name: str,
        source_connection_id: UUID,
        destination_connection_ids: List[UUID],
        cron_schedule: Optional[str],
        run_immediately: bool,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> Tuple[schemas.Sync, Optional[schemas.SyncJob]]:
        """Create a Sync record and optionally a PENDING SyncJob.

        All writes happen inside the caller's UoW (no commit).
        """
        sync_in = SyncCreate(
            name=name,
            source_connection_id=source_connection_id,
            destination_connection_ids=destination_connection_ids,
            cron_schedule=cron_schedule,
            status=SyncStatus.ACTIVE,
            run_immediately=run_immediately,
        )

        sync_schema = await self._sync_repo.create(
            uow.session,
            obj_in=sync_in,
            ctx=ctx,
            uow=uow,
        )

        sync_job_schema: Optional[schemas.SyncJob] = None
        if run_immediately:
            sync_job = await self._sync_job_repo.create(
                uow.session,
                SyncJobCreate(sync_id=sync_schema.id, status=SyncJobStatus.PENDING),
                ctx,
                uow=uow,
            )
            sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)

        return sync_schema, sync_job_schema

    async def trigger_sync_run(
        self,
        db: AsyncSession,
        sync_id: UUID,
        ctx: ApiContext,
    ) -> Tuple[schemas.Sync, schemas.SyncJob]:
        """Trigger a manual sync run.

        Checks for existing active jobs, fetches the sync with
        connections, creates a new SyncJob inside a UoW, and returns
        both schemas.

        Raises:
            HTTPException 400: if a job is already active.
            ValueError: if the sync is not found.
        """
        active_jobs = await self._sync_job_repo.get_active_for_sync(db, sync_id, ctx)
        if active_jobs:
            job_status = active_jobs[0].status.lower()
            raise HTTPException(
                status_code=400,
                detail=f"Cannot start new sync: a sync job is already {job_status}",
            )

        sync = await self._sync_repo.get(db, sync_id, ctx)
        if not sync:
            raise ValueError(f"Sync {sync_id} not found")

        sync_schema = schemas.Sync.model_validate(sync, from_attributes=True)

        async with UnitOfWork(db) as uow:
            sync_job = await self._sync_job_repo.create(
                uow.session,
                schemas.SyncJobCreate(
                    sync_id=sync_id,
                    status=SyncJobStatus.PENDING,
                ),
                ctx,
                uow=uow,
            )
            await uow.commit()
            await uow.session.refresh(sync_job)
            sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)

        return sync_schema, sync_job_schema
