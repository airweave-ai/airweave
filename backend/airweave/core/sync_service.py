"""Refactored sync service with Temporal-only execution."""

from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.shared_models import SyncJobStatus
from airweave.core.sync_job_service import sync_job_service
from airweave.db.session import get_db_context
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.models.sync import Sync
from airweave.models.sync_job import SyncJob
from airweave.platform.sync.config import SyncConfig
from airweave.platform.sync.factory import SyncFactory
from airweave.platform.temporal.schedule_service import temporal_schedule_service


class SyncService:
    """Refactored sync service with Temporal-only execution.

    Key changes:
    - No background tasks or local scheduling
    - All execution through Temporal
    - Clean separation of sync management from execution
    """

    async def create_and_run_sync(
        self,
        db: AsyncSession,
        sync_in: schemas.SyncCreate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Tuple[Sync, Optional[SyncJob]]:
        """Create a sync and optionally trigger initial run.

        Args:
            db: Database session
            sync_in: Sync creation schema
            ctx: API context
            uow: Optional unit of work for transaction management

        Returns:
            Tuple of (sync, sync_job) where sync_job is None if not run immediately
        """
        if uow:
            return await self._create_and_run_with_uow(uow.session, sync_in, ctx, uow)
        else:
            async with UnitOfWork(db) as uow:
                return await self._create_and_run_with_uow(uow.session, sync_in, ctx, uow)

    async def _create_and_run_with_uow(
        self,
        db: AsyncSession,
        sync_in: schemas.SyncCreate,
        ctx: ApiContext,
        uow: UnitOfWork,
        skip_temporal_schedule: bool = False,
    ) -> Tuple[Sync, Optional[SyncJob]]:
        """Internal method to create sync within a transaction.

        Args:
            db: Database session
            sync_in: Sync creation schema
            ctx: API context
            uow: Unit of work for transaction management
            skip_temporal_schedule: If True, skip creating Temporal schedule (for deferred creation)
        """
        # Create sync
        sync = await crud.sync.create(db, obj_in=sync_in, ctx=ctx, uow=uow)
        await db.flush()

        # Schedule in Temporal if cron schedule provided (unless skipped)
        if sync_in.cron_schedule and not skip_temporal_schedule:
            await temporal_schedule_service.create_or_update_schedule(
                sync_id=sync.id,
                cron_schedule=sync_in.cron_schedule,
                db=db,
                ctx=ctx,
                uow=uow,
            )

        # Run immediately if requested
        sync_job = None
        if sync_in.run_immediately:
            sync_job = await self._create_sync_job(db, sync.id, ctx, uow)
            # Note: We'll trigger Temporal after the transaction commits

        return sync, sync_job

    async def run(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.CollectionRecord,
        source_connection: schemas.Connection,
        ctx: ApiContext,
        dense_embedder: DenseEmbedderProtocol,
        sparse_embedder: SparseEmbedderProtocol,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
        execution_config: Optional[SyncConfig] = None,
    ) -> schemas.Sync:
        """Run a sync.

        Args:
        ----
            sync (schemas.Sync): The sync to run.
            sync_job (schemas.SyncJob): The sync job to run.
            collection (schemas.CollectionRecord): The collection to sync.
            source_connection (schemas.Connection): The source connection to sync.
            ctx (ApiContext): The API context.
            access_token (Optional[str]): Optional access token to use
                instead of stored credentials.
            force_full_sync (bool): If True, forces a full sync with orphaned entity deletion.
            execution_config (Optional[SyncConfig]): Optional execution config
                for controlling sync behavior (destination filtering, handler toggles, etc.)
            dense_embedder: Domain dense embedder instance.
            sparse_embedder: Domain sparse embedder instance.

        Returns:
        -------
            schemas.Sync: The sync.
        """
        try:
            async with get_db_context() as db:
                orchestrator = await SyncFactory.create_orchestrator(
                    db=db,
                    sync=sync,
                    sync_job=sync_job,
                    collection=collection,
                    connection=source_connection,
                    ctx=ctx,
                    access_token=access_token,
                    force_full_sync=force_full_sync,
                    execution_config=execution_config,
                    dense_embedder=dense_embedder,
                    sparse_embedder=sparse_embedder,
                )
        except Exception as e:
            ctx.logger.error(f"Error during sync orchestrator creation: {e}")
            # Fail the sync job if orchestrator creation failed
            await sync_job_service.update_status(
                sync_job_id=sync_job.id,
                status=SyncJobStatus.FAILED,
                ctx=ctx,
                error=str(e),
                failed_at=utc_now_naive(),
            )
            raise e

        # Run the sync with the dedicated orchestrator instance
        return await orchestrator.run()

    async def trigger_sync_run(
        self,
        db: AsyncSession,
        sync_id: UUID,
        ctx: ApiContext,
        execution_config: Optional[Dict[str, Any]] = None,
        sync_metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[schemas.Sync, schemas.SyncJob]:
        """Trigger a manual sync run.

        Args:
            db: Database session
            sync_id: Sync ID to run
            ctx: API context
            execution_config: Optional execution config dict to persist in DB
            sync_metadata: Optional metadata dict (e.g., tags) to persist in DB

        Returns:
            Tuple of (sync, sync_job) schemas

        Raises:
            HTTPException: If a sync job is already running or pending
        """
        # Check for existing active jobs to prevent concurrent runs
        active_jobs = await crud.sync_job.get_all_by_sync_id(
            db,
            sync_id=sync_id,
            status=[
                SyncJobStatus.PENDING.value,
                SyncJobStatus.RUNNING.value,
                SyncJobStatus.CANCELLING.value,
            ],
        )

        if active_jobs:
            job_status = active_jobs[0].status.lower()
            raise HTTPException(
                status_code=400, detail=f"Cannot start new sync: a sync job is already {job_status}"
            )

        # Get sync with connections
        sync = await crud.sync.get(db, id=sync_id, ctx=ctx, with_connections=True)
        if not sync:
            raise ValueError(f"Sync {sync_id} not found")

        # Convert to schemas
        sync_schema = schemas.Sync.model_validate(sync, from_attributes=True)

        # Create sync job
        async with UnitOfWork(db) as uow:
            sync_job = await self._create_sync_job(
                uow.session, sync_id, ctx, uow, execution_config, sync_metadata
            )

            await uow.commit()
            await uow.session.refresh(sync_job)
            sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)

        return sync_schema, sync_job_schema

    async def _create_sync_job(
        self,
        db: AsyncSession,
        sync_id: UUID,
        ctx: ApiContext,
        uow: UnitOfWork,
        execution_config: Optional[Dict[str, Any]] = None,
        sync_metadata: Optional[Dict[str, Any]] = None,
    ) -> SyncJob:
        """Create a sync job record."""
        sync_job_in = schemas.SyncJobCreate(
            sync_id=sync_id,
            status=SyncJobStatus.PENDING,
            sync_config=execution_config.model_dump() if execution_config else None,
            sync_metadata=sync_metadata,
        )

        return await crud.sync_job.create(db, obj_in=sync_job_in, ctx=ctx, uow=uow)

    async def list_sync_jobs(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        sync_id: UUID,
        limit: int = 100,
    ) -> List[SyncJob]:
        """List sync jobs for a sync."""
        return await crud.sync_job.get_all_by_sync_id(db, sync_id=sync_id)

    async def get_last_sync_job(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        sync_id: UUID,
    ) -> Optional[SyncJob]:
        """Get the last sync job for a sync."""
        return await crud.sync_job.get_latest_by_sync_id(db, sync_id=sync_id)

    async def get_sync_job(
        self,
        db: AsyncSession,
        job_id: UUID,
        ctx: ApiContext,
        sync_id: Optional[UUID] = None,
    ) -> Optional[SyncJob]:
        """Get a specific sync job."""
        job = await crud.sync_job.get(db, id=job_id, ctx=ctx)

        # Verify it belongs to the expected sync if provided
        if job and sync_id and job.sync_id != sync_id:
            return None

        return job

    async def update_sync_schedule(
        self,
        db: AsyncSession,
        sync_id: UUID,
        cron_schedule: Optional[str],
        ctx: ApiContext,
    ) -> Sync:
        """Update sync schedule.

        Args:
            db: Database session
            sync_id: Sync ID
            cron_schedule: New cron schedule (None to disable)
            ctx: API context

        Returns:
            Updated sync
        """
        sync = await crud.sync.get(db, id=sync_id, ctx=ctx)
        if not sync:
            raise ValueError(f"Sync {sync_id} not found")

        async with UnitOfWork(db) as uow:
            # Update sync
            sync_update = schemas.SyncUpdate(cron_schedule=cron_schedule)
            sync = await crud.sync.update(
                uow.session,
                db_obj=sync,
                obj_in=sync_update,
                ctx=ctx,
                uow=uow,
            )

            # Update Temporal schedule
            if cron_schedule:
                await temporal_schedule_service.create_or_update_schedule(
                    sync_id=sync_id,
                    cron_schedule=cron_schedule,
                    db=uow.session,
                    ctx=ctx,
                )
            else:
                await temporal_schedule_service.delete_schedule(
                    sync_id=sync_id,
                    db=uow.session,
                    ctx=ctx,
                )

            await uow.commit()

        return sync

    async def delete_sync(
        self,
        db: AsyncSession,
        sync_id: UUID,
        ctx: ApiContext,
    ) -> None:
        """Delete a sync and all related data.

        Args:
            db: Database session
            sync_id: Sync ID to delete
            ctx: API context
        """
        # Clean up Temporal schedules
        await temporal_schedule_service.delete_all_schedules_for_sync(
            sync_id=sync_id,
            db=db,
            ctx=ctx,
        )

        # Delete sync (cascades to jobs)
        await crud.sync.remove(db, id=sync_id, ctx=ctx)

    async def get_sync_status(
        self,
        db: AsyncSession,
        sync_id: UUID,
        ctx: ApiContext,
    ) -> Dict:
        """Get comprehensive sync status.

        Args:
            db: Database session
            sync_id: Sync ID
            ctx: API context

        Returns:
            Dictionary with sync status information
        """
        sync = await crud.sync.get(db, id=sync_id, ctx=ctx)
        if not sync:
            raise ValueError(f"Sync {sync_id} not found")

        # Get latest job
        jobs = await self.list_sync_jobs(db, ctx=ctx, sync_id=sync_id, limit=1)
        latest_job = jobs[0] if jobs else None

        # Get job statistics
        job_stats = await crud.sync_job.get_statistics(db, sync_id=sync_id, ctx=ctx)

        return {
            "sync_id": sync_id,
            "status": sync.status,
            "cron_schedule": sync.cron_schedule,
            "next_scheduled_run": sync.next_scheduled_run,
            "latest_job": (
                {
                    "id": latest_job.id,
                    "status": latest_job.status,
                    "started_at": latest_job.started_at,
                    "completed_at": latest_job.completed_at,
                }
                if latest_job
                else None
            ),
            "statistics": job_stats,
        }


# Singleton instance
sync_service = SyncService()
