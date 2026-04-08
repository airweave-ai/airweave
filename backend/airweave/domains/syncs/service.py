"""Unified sync service — single transactional interface for the syncs domain.

Consolidates SyncRecordService, SyncLifecycleService, and the sync runner
into one service with clean, directed semantics. All callers interact through
this interface; internal implementation details (state machines, repos) are hidden.

Methods speak the sync domain language: create, get, pause, resume, delete,
trigger_run, cancel_job, get_jobs, run. No source_connection types cross
this boundary.
"""

import asyncio
import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.constants.reserved_ids import NATIVE_VESPA_UUID
from airweave.core.context import BaseContext
from airweave.core.shared_models import SyncJobStatus, SyncStatus
from airweave.db.session import get_db_context
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.sources.exceptions.classifier import classify_error
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.domains.sync_pipeline.config import SyncConfig
from airweave.domains.sync_pipeline.protocols import SyncFactoryProtocol
from airweave.domains.syncs.jobs.protocols import (
    SyncJobRepositoryProtocol,
    SyncJobStateMachineProtocol,
)
from airweave.domains.syncs.protocols import (
    SyncCursorRepositoryProtocol,
    SyncRepositoryProtocol,
    SyncServiceProtocol,
    SyncStateMachineProtocol,
)
from airweave.domains.syncs.types import (
    CONTINUOUS_SOURCE_DEFAULT_CRON,
    DAILY_CRON_TEMPLATE,
    SyncProvisionResult,
    SyncTransitionResult,
)
from airweave.domains.temporal.protocols import (
    TemporalScheduleServiceProtocol,
    TemporalWorkflowServiceProtocol,
)
from airweave.schemas.source_connection import ScheduleConfig
from airweave.schemas.sync import SyncCreate
from airweave.schemas.sync_job import SyncJobCreate

_SUB_HOURLY_PATTERN = re.compile(r"^\*/([1-5]?[0-9]) \* \* \* \*$")


class SyncService(SyncServiceProtocol):
    """Unified sync service — the public interface for the syncs domain.

    Callers use directed methods (create, pause, resume, delete) rather than
    raw state transitions. The state machine is an internal implementation detail.
    """

    def __init__(  # noqa: D107
        self,
        sync_repo: SyncRepositoryProtocol,
        sync_job_repo: SyncJobRepositoryProtocol,
        sync_cursor_repo: SyncCursorRepositoryProtocol,
        state_machine: SyncStateMachineProtocol,
        job_state_machine: SyncJobStateMachineProtocol,
        temporal_workflow_service: TemporalWorkflowServiceProtocol,
        temporal_schedule_service: TemporalScheduleServiceProtocol,
        sync_factory: SyncFactoryProtocol,
    ) -> None:
        self._sync_repo = sync_repo
        self._sync_job_repo = sync_job_repo
        self._sync_cursor_repo = sync_cursor_repo
        self._state_machine = state_machine
        self._job_state_machine = job_state_machine
        self._temporal_workflow_service = temporal_workflow_service
        self._temporal_schedule_service = temporal_schedule_service
        self._sync_factory = sync_factory

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def create(
        self,
        db: AsyncSession,
        *,
        name: str,
        source_connection_id: UUID,
        destination_connection_ids: List[UUID],
        collection_id: UUID,
        collection_readable_id: str,
        source_entry: SourceRegistryEntry,
        schedule_config: Optional[ScheduleConfig],
        run_immediately: bool,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> SyncProvisionResult:
        """Create sync + optional job + Temporal schedule atomically.

        Raises ValueError if called for federated sources or when there is
        neither a schedule nor an immediate run request — callers must guard
        these cases before calling create.
        """
        if source_entry.federated_search:
            raise ValueError(f"Cannot create sync for federated source '{source_entry.short_name}'")

        cron = self._resolve_cron(schedule_config, source_entry, ctx)

        if not cron and not run_immediately:
            raise ValueError("Cannot create sync: no schedule and run_immediately=False")

        if cron:
            self._validate_cron_for_source(cron, source_entry)

        sync_schema, sync_job_schema = await self._create_sync_records(
            uow.session,
            name=f"Sync for {name}",
            source_connection_id=source_connection_id,
            destination_connection_ids=destination_connection_ids,
            cron_schedule=cron,
            run_immediately=run_immediately,
            ctx=ctx,
            uow=uow,
        )

        if cron:
            await self._temporal_schedule_service.create_or_update_schedule(
                sync_id=sync_schema.id,
                cron_schedule=cron,
                db=uow.session,
                ctx=ctx,
                uow=uow,
                collection_readable_id=collection_readable_id,
                connection_id=source_connection_id,
            )

        return SyncProvisionResult(
            sync_id=sync_schema.id,
            sync=sync_schema,
            sync_job=sync_job_schema,
            cron_schedule=cron,
        )

    async def get(self, db: AsyncSession, *, sync_id: UUID, ctx: BaseContext) -> schemas.Sync:
        """Get a sync by ID."""
        sync = await self._sync_repo.get(db, sync_id, ctx)
        if not sync:
            raise HTTPException(status_code=404, detail=f"Sync {sync_id} not found")
        return sync

    async def pause(
        self,
        sync_id: UUID,
        ctx: BaseContext,
        *,
        reason: str = "",
    ) -> SyncTransitionResult:
        """Pause a sync: update DB status, pause Temporal schedules."""
        return await self._state_machine.transition(
            sync_id=sync_id, target=SyncStatus.PAUSED, ctx=ctx, reason=reason
        )

    async def resume(
        self,
        sync_id: UUID,
        ctx: BaseContext,
        *,
        reason: str = "",
    ) -> SyncTransitionResult:
        """Resume a paused sync: update DB status, unpause Temporal schedules."""
        return await self._state_machine.transition(
            sync_id=sync_id, target=SyncStatus.ACTIVE, ctx=ctx, reason=reason
        )

    async def delete(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        collection_id: UUID,
        organization_id: UUID,
        ctx: ApiContext,
        cancel_timeout_seconds: int = 15,
    ) -> None:
        """Cancel active workflows and schedule async cleanup for a single sync.

        1. Cancels PENDING/RUNNING workflows via Temporal.
        2. Polls until terminal state (up to cancel_timeout_seconds).
        3. Schedules async cleanup workflow for Vespa/ARF/schedules.

        The caller is responsible for the CASCADE delete of DB records.
        """
        needs_wait = await self._cancel_active_sync(db, sync_id, ctx)
        if needs_wait:
            await self._wait_for_terminal(db, sync_id, cancel_timeout_seconds, ctx)
        await self._schedule_cleanup(sync_id, collection_id, organization_id, ctx)

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    async def resolve_destination_ids(self, db: AsyncSession, ctx: ApiContext) -> List[UUID]:
        """Resolve destination connection IDs."""
        return [NATIVE_VESPA_UUID]

    async def trigger_run(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        collection: schemas.CollectionRecord,
        connection: schemas.Connection,
        ctx: ApiContext,
        force_full_sync: bool = False,
    ) -> Tuple[schemas.Sync, schemas.SyncJob]:
        """Create a PENDING job and start the Temporal workflow.

        Validates the sync is ACTIVE and no active jobs exist, creates the
        job record, then starts the Temporal workflow.
        """
        sync = await self._sync_repo.get(db, sync_id, ctx)
        if not sync:
            raise HTTPException(status_code=404, detail=f"Sync {sync_id} not found")

        if SyncStatus(sync.status) != SyncStatus.ACTIVE:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot trigger sync: sync is {sync.status}",
            )

        active_jobs = await self._sync_job_repo.get_active_for_sync(db, sync_id, ctx)
        if active_jobs:
            job_status = active_jobs[0].status.lower()
            raise HTTPException(
                status_code=400,
                detail=f"Cannot start new sync: a sync job is already {job_status}",
            )

        sync_schema = schemas.Sync.model_validate(sync, from_attributes=True)

        sync_job = await self._sync_job_repo.create(
            db,
            SyncJobCreate(sync_id=sync_id, status=SyncJobStatus.PENDING),
            ctx,
        )
        await db.flush()
        await db.refresh(sync_job)
        sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)

        await self._temporal_workflow_service.run_source_connection_workflow(
            sync=sync_schema,
            sync_job=sync_job_schema,
            collection=collection,
            connection=connection,
            ctx=ctx,
            force_full_sync=force_full_sync,
        )

        return sync_schema, sync_job_schema

    async def get_jobs(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        ctx: ApiContext,
        limit: int = 100,
    ) -> List[schemas.SyncJob]:
        """List jobs for a sync, most recent first."""
        jobs = await self._sync_job_repo.get_all_by_sync_id(db, sync_id, ctx, limit=limit)
        return [schemas.SyncJob.model_validate(j, from_attributes=True) for j in jobs]

    async def cancel_job(
        self,
        db: AsyncSession,
        *,
        job_id: UUID,
        ctx: ApiContext,
    ) -> schemas.SyncJob:
        """Cancel a running sync job.

        Transitions to CANCELLING, sends cancel to Temporal, and handles
        edge cases (workflow not found, Temporal failure with one retry).
        """
        sync_job = await self._sync_job_repo.get(db, job_id, ctx)
        if not sync_job:
            raise HTTPException(status_code=404, detail="Sync job not found")

        if sync_job.status not in (SyncJobStatus.PENDING, SyncJobStatus.RUNNING):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel job in {sync_job.status} state",
            )

        await self._job_state_machine.transition(
            sync_job_id=job_id, target=SyncJobStatus.CANCELLING, ctx=ctx
        )

        cancel_result = await self._cancel_temporal_workflow_with_retry(job_id, ctx)

        if not cancel_result["success"]:
            raise HTTPException(
                status_code=502, detail="Failed to request cancellation from Temporal"
            )

        if not cancel_result["workflow_found"]:
            # NOT_FOUND means the workflow already completed, never started,
            # or was cleaned up. Check current DB state before marking cancelled.
            await db.refresh(sync_job)
            terminal = {SyncJobStatus.COMPLETED, SyncJobStatus.FAILED, SyncJobStatus.CANCELLED}
            if sync_job.status not in terminal:
                ctx.logger.info(f"Workflow not found for job {job_id}, marking CANCELLED")
                await self._job_state_machine.transition(
                    sync_job_id=job_id, target=SyncJobStatus.CANCELLED, ctx=ctx
                )

        await db.refresh(sync_job)
        return schemas.SyncJob.model_validate(sync_job, from_attributes=True)

    async def _cancel_temporal_workflow_with_retry(
        self, job_id: UUID, ctx: ApiContext, max_retries: int = 1
    ) -> dict[str, bool]:
        """Send cancellation to Temporal with a single retry on RPC failure."""
        for attempt in range(1 + max_retries):
            result = await self._temporal_workflow_service.cancel_sync_job_workflow(
                str(job_id), ctx
            )
            if result["success"] or result["workflow_found"]:
                return result
            if attempt < max_retries:
                await asyncio.sleep(0.5)
                ctx.logger.info(f"Retrying cancel for job {job_id} (attempt {attempt + 2})")
        return result

    async def validate_force_full_sync(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> None:
        """Log force_full_sync intent. No-op if no cursor (already a full sync)."""
        cursor = await self._sync_cursor_repo.get_by_sync_id(db, sync_id, ctx)
        if not cursor or not cursor.cursor_data:
            ctx.logger.info(
                f"force_full_sync requested but no cursor data exists for sync {sync_id}. "
                "This sync will perform a full sync by default."
            )
            return
        ctx.logger.info(
            f"Force full sync requested for continuous sync {sync_id}. "
            "Will ignore cursor data and perform full sync with orphaned entity cleanup."
        )

    # ------------------------------------------------------------------
    # Execution (Temporal activity entry point)
    # ------------------------------------------------------------------

    async def run(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.CollectionRecord,
        source_connection: schemas.Connection,
        ctx: ApiContext,
        force_full_sync: bool = False,
        execution_config: Optional[SyncConfig] = None,
        access_token: Optional[str] = None,
    ) -> schemas.Sync:
        """Run a sync via SyncFactory + SyncOrchestrator.

        Called exclusively from RunSyncActivity (Temporal worker).
        """
        try:
            async with get_db_context() as db:
                orchestrator = await self._sync_factory.create_orchestrator(
                    db=db,
                    sync=sync,
                    sync_job=sync_job,
                    collection=collection,
                    connection=source_connection,
                    ctx=ctx,
                    force_full_sync=force_full_sync,
                    execution_config=execution_config,
                    access_token=access_token,
                )
        except Exception as e:
            ctx.logger.error(f"Error during sync orchestrator creation: {e}")

            classification = classify_error(e)

            await self._job_state_machine.transition(
                sync_job_id=sync_job.id,
                target=SyncJobStatus.FAILED,
                ctx=ctx,
                error=str(e),
                error_category=classification.category,
            )

            if classification.category is not None and sync:
                try:
                    await self._state_machine.transition(
                        sync_id=sync.id,
                        target=SyncStatus.PAUSED,
                        ctx=ctx,
                        reason=f"Credential error: {classification.category.value}",
                    )
                except Exception:
                    ctx.logger.warning("Failed to pause sync after credential error", exc_info=True)

            raise e

        return await orchestrator.run()

    # ------------------------------------------------------------------
    # Private: record creation
    # ------------------------------------------------------------------

    async def _create_sync_records(
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

        sync_schema = await self._sync_repo.create(uow.session, obj_in=sync_in, ctx=ctx, uow=uow)
        await uow.session.flush()

        sync_job_schema: Optional[schemas.SyncJob] = None
        if run_immediately:
            sync_job = await self._sync_job_repo.create(
                uow.session,
                SyncJobCreate(sync_id=sync_schema.id, status=SyncJobStatus.PENDING),
                ctx,
                uow=uow,
            )
            await uow.session.flush()
            await uow.session.refresh(sync_job)
            sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)

        return sync_schema, sync_job_schema

    # ------------------------------------------------------------------
    # Private: cron resolution
    # ------------------------------------------------------------------

    def _resolve_cron(
        self,
        schedule_config: Optional[ScheduleConfig],
        source_entry: SourceRegistryEntry,
        ctx: ApiContext,
    ) -> Optional[str]:
        """Resolve cron schedule from config or source defaults."""
        if schedule_config is not None:
            if schedule_config.cron is not None:
                return schedule_config.cron
            ctx.logger.info("Schedule cron explicitly null, no schedule")
            return None

        if source_entry.supports_continuous:
            ctx.logger.info("Continuous source, defaulting to 5-minute schedule")
            return CONTINUOUS_SOURCE_DEFAULT_CRON

        now_utc = datetime.now(timezone.utc)
        cron = DAILY_CRON_TEMPLATE.format(minute=now_utc.minute, hour=now_utc.hour)
        ctx.logger.info(f"Defaulting to daily at {now_utc.hour:02d}:{now_utc.minute:02d} UTC")
        return cron

    def _validate_cron_for_source(self, cron: str, source_entry: SourceRegistryEntry) -> None:
        """Reject sub-hourly schedules for non-continuous sources."""
        if source_entry.supports_continuous:
            return

        if cron == "* * * * *":
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Source '{source_entry.short_name}' does not support "
                    f"continuous syncs. Minimum interval is 1 hour."
                ),
            )

        match = _SUB_HOURLY_PATTERN.match(cron)
        if match and int(match.group(1)) < 60:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Source '{source_entry.short_name}' does not support "
                    f"continuous syncs. Minimum interval is 1 hour."
                ),
            )

    # ------------------------------------------------------------------
    # Private: delete helpers
    # ------------------------------------------------------------------

    async def _cancel_active_sync(
        self,
        db: AsyncSession,
        sync_id: UUID,
        ctx: ApiContext,
    ) -> bool:
        """Cancel PENDING/RUNNING job for a sync. Returns True if it needs waiting."""
        non_terminal = {SyncJobStatus.PENDING, SyncJobStatus.RUNNING, SyncJobStatus.CANCELLING}
        latest_job = await self._sync_job_repo.get_latest_by_sync_id(db, sync_id=sync_id)
        if not latest_job or latest_job.status not in non_terminal:
            return False
        if latest_job.status in (SyncJobStatus.PENDING, SyncJobStatus.RUNNING):
            try:
                await self._temporal_workflow_service.cancel_sync_job_workflow(
                    str(latest_job.id), ctx
                )
                ctx.logger.info(f"Cancelled job {latest_job.id} before deletion")
            except Exception as e:
                ctx.logger.warning(f"Failed to cancel job {latest_job.id}: {e}")
        return True

    async def _wait_for_terminal(
        self,
        db: AsyncSession,
        sync_id: UUID,
        timeout_seconds: int,
        ctx: ApiContext,
    ) -> None:
        """Poll until the sync's latest job reaches a terminal state or timeout."""
        terminal = {SyncJobStatus.COMPLETED, SyncJobStatus.FAILED, SyncJobStatus.CANCELLED}
        elapsed = 0.0
        while elapsed < timeout_seconds:
            await asyncio.sleep(1.0)
            elapsed += 1.0
            db.expire_all()
            job = await self._sync_job_repo.get_latest_by_sync_id(db, sync_id=sync_id)
            if not job or job.status in terminal:
                return
        ctx.logger.warning(
            f"Sync {sync_id} did not reach terminal state "
            f"within {timeout_seconds}s -- proceeding with deletion anyway"
        )

    async def _schedule_cleanup(
        self,
        sync_id: UUID,
        collection_id: UUID,
        organization_id: UUID,
        ctx: ApiContext,
    ) -> None:
        """Schedule a Temporal workflow for async Vespa/ARF cleanup."""
        try:
            await self._temporal_workflow_service.start_cleanup_sync_data_workflow(
                sync_ids=[str(sync_id)],
                collection_id=str(collection_id),
                organization_id=str(organization_id),
                ctx=ctx,
            )
        except Exception as e:
            ctx.logger.error(
                f"Failed to schedule async cleanup for sync {sync_id}: {e}. "
                f"Data may be orphaned in Vespa/ARF."
            )
