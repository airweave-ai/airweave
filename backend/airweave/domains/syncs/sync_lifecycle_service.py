"""Sync lifecycle service: provision, run, get_jobs, cancel_job, teardown."""

import asyncio
import re
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.events.sync import SyncLifecycleEvent
from airweave.core.protocols.event_bus import EventBus
from airweave.core.shared_models import SyncJobStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.connections.protocols import ConnectionRepositoryProtocol
from airweave.domains.source_connections.protocols import (
    ResponseBuilderProtocol,
    SourceConnectionRepositoryProtocol,
)
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.domains.syncs.protocols import (
    SyncCursorRepositoryProtocol,
    SyncJobRepositoryProtocol,
    SyncJobServiceProtocol,
    SyncLifecycleServiceProtocol,
    SyncRecordServiceProtocol,
)
from airweave.domains.syncs.types import (
    CONTINUOUS_SOURCE_DEFAULT_CRON,
    DAILY_CRON_TEMPLATE,
    SyncProvisionResult,
)
from airweave.domains.temporal.protocols import (
    TemporalScheduleServiceProtocol,
    TemporalWorkflowServiceProtocol,
)
from airweave.schemas.source_connection import ScheduleConfig, SourceConnectionJob

_SUB_HOURLY_PATTERN = re.compile(r"^\*/([1-5]?[0-9]) \* \* \* \*$")


class SyncLifecycleService(SyncLifecycleServiceProtocol):
    """API-facing facade for sync lifecycle: provision, run, get_jobs, cancel_job."""

    def __init__(
        self,
        sc_repo: SourceConnectionRepositoryProtocol,
        collection_repo: CollectionRepositoryProtocol,
        connection_repo: ConnectionRepositoryProtocol,
        sync_cursor_repo: SyncCursorRepositoryProtocol,
        sync_service: SyncRecordServiceProtocol,
        sync_job_service: SyncJobServiceProtocol,
        sync_job_repo: SyncJobRepositoryProtocol,
        temporal_workflow_service: TemporalWorkflowServiceProtocol,
        temporal_schedule_service: TemporalScheduleServiceProtocol,
        response_builder: ResponseBuilderProtocol,
        event_bus: EventBus,
    ) -> None:
        """Initialize with all injected dependencies."""
        self._sc_repo = sc_repo
        self._collection_repo = collection_repo
        self._connection_repo = connection_repo
        self._sync_cursor_repo = sync_cursor_repo
        self._sync_service = sync_service
        self._sync_job_service = sync_job_service
        self._sync_job_repo = sync_job_repo
        self._temporal_workflow_service = temporal_workflow_service
        self._temporal_schedule_service = temporal_schedule_service
        self._response_builder = response_builder
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Public API (protocol surface)
    # ------------------------------------------------------------------

    async def teardown_syncs_for_collection(
        self,
        db: AsyncSession,
        *,
        sync_ids: List[UUID],
        collection_id: UUID,
        organization_id: UUID,
        ctx: ApiContext,
        cancel_timeout_seconds: int = 15,
    ) -> None:
        """Cancel running workflows and schedule async cleanup for a collection's syncs.

        1. Cancels PENDING/RUNNING workflows via Temporal.
        2. Polls until terminal state (up to cancel_timeout_seconds).
        3. Schedules async cleanup workflow for Vespa/ARF/schedules.
        """
        syncs_to_wait = await self._cancel_active_syncs(db, sync_ids, ctx)
        await self._wait_for_terminal(db, syncs_to_wait, cancel_timeout_seconds, ctx)
        await self._schedule_collection_cleanup(sync_ids, collection_id, organization_id, ctx)

    async def provision_sync(
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
    ) -> Optional[SyncProvisionResult]:
        """Create sync + job + Temporal schedule atomically.

        Returns None for federated search sources (no sync needed)
        or when there is neither a schedule nor an immediate run.
        """
        if source_entry.federated_search:
            ctx.logger.info(f"Skipping sync for federated source '{source_entry.short_name}'")
            return None

        cron = self._resolve_cron(schedule_config, source_entry, ctx)

        if not cron and not run_immediately:
            ctx.logger.info("No cron schedule and run_immediately=False, skipping sync creation")
            return None

        if cron:
            self._validate_cron_for_source(cron, source_entry)

        sync_schema, sync_job_schema = await self._sync_service.create_sync(
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

    async def run(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
        force_full_sync: bool = False,
    ) -> SourceConnectionJob:
        """Trigger a sync run for a source connection.

        Args:
            db: Database session.
            id: Source connection ID.
            ctx: API context.
            force_full_sync: Only valid for continuous syncs.
        """
        source_conn = await self._sc_repo.get(db, id, ctx)
        if not source_conn:
            raise HTTPException(status_code=404, detail="Source connection not found")
        if not source_conn.sync_id:
            raise HTTPException(status_code=400, detail="Source connection has no associated sync")

        sc_id = source_conn.id
        sc_sync_id = source_conn.sync_id

        if force_full_sync:
            await self._validate_force_full_sync(db, sc_sync_id, ctx)

        collection = await self._collection_repo.get_by_readable_id(
            db, source_conn.readable_collection_id, ctx
        )
        collection_schema = schemas.Collection.model_validate(collection, from_attributes=True)

        connection_schema = await self._resolve_connection(db, source_conn, ctx)

        sync, sync_job = await self._sync_service.trigger_sync_run(db, sync_id=sc_sync_id, ctx=ctx)
        sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)

        await self._event_bus.publish(
            SyncLifecycleEvent.pending(
                organization_id=ctx.organization.id,
                source_connection_id=sc_id,
                sync_job_id=sync_job_schema.id,
                sync_id=sc_sync_id,
                collection_id=collection_schema.id,
                source_type=connection_schema.short_name,
                collection_name=collection_schema.name,
                collection_readable_id=collection_schema.readable_id,
            )
        )

        await self._temporal_workflow_service.run_source_connection_workflow(
            sync=sync,
            sync_job=sync_job,
            collection=collection_schema,
            connection=connection_schema,
            ctx=ctx,
            force_full_sync=force_full_sync,
        )

        return sync_job_schema.to_source_connection_job(sc_id)

    async def get_jobs(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
        limit: int = 100,
    ) -> List[SourceConnectionJob]:
        """Get sync jobs for a source connection."""
        source_conn = await self._sc_repo.get(db, id, ctx)
        if not source_conn:
            raise HTTPException(status_code=404, detail="Source connection not found")
        if not source_conn.sync_id:
            return []

        jobs = await self._sync_job_repo.get_all_by_sync_id(db, source_conn.sync_id, ctx)
        return [self._response_builder.map_sync_job(j, source_conn.id) for j in jobs]

    async def cancel_job(
        self,
        db: AsyncSession,
        *,
        source_connection_id: UUID,
        job_id: UUID,
        ctx: ApiContext,
    ) -> SourceConnectionJob:
        """Cancel a running sync job.

        Sets CANCELLING, sends cancel to Temporal, and handles
        edge cases (workflow not found, Temporal failure).
        """
        source_conn = await self._sc_repo.get(db, source_connection_id, ctx)
        if not source_conn:
            raise HTTPException(status_code=404, detail="Source connection not found")
        if not source_conn.sync_id:
            raise HTTPException(status_code=400, detail="Source connection has no associated sync")

        sync_job = await self._sync_job_repo.get(db, job_id, ctx)
        if not sync_job:
            raise HTTPException(status_code=404, detail="Sync job not found")
        if sync_job.sync_id != source_conn.sync_id:
            raise HTTPException(
                status_code=400,
                detail="Sync job does not belong to this source connection",
            )
        if sync_job.status not in (SyncJobStatus.PENDING, SyncJobStatus.RUNNING):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel job in {sync_job.status} state",
            )

        original_status = sync_job.status

        await self._sync_job_service.update_status(
            sync_job_id=job_id, status=SyncJobStatus.CANCELLING, ctx=ctx
        )

        cancel_result = await self._temporal_workflow_service.cancel_sync_job_workflow(
            str(job_id), ctx
        )

        if not cancel_result["success"]:
            fallback = (
                SyncJobStatus.RUNNING
                if original_status == SyncJobStatus.RUNNING
                else SyncJobStatus.PENDING
            )
            await self._sync_job_service.update_status(sync_job_id=job_id, status=fallback, ctx=ctx)
            raise HTTPException(
                status_code=502, detail="Failed to request cancellation from Temporal"
            )

        if not cancel_result["workflow_found"]:
            ctx.logger.info(f"Workflow not found for job {job_id} - marking CANCELLED directly")
            await self._sync_job_service.update_status(
                sync_job_id=job_id,
                status=SyncJobStatus.CANCELLED,
                ctx=ctx,
                completed_at=utc_now_naive(),
                error="Workflow not found in Temporal - may have already completed",
            )

        await db.refresh(sync_job)
        sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
        return sync_job_schema.to_source_connection_job(source_connection_id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _cancel_active_syncs(
        self,
        db: AsyncSession,
        sync_ids: List[UUID],
        ctx: ApiContext,
    ) -> List[UUID]:
        """Cancel PENDING/RUNNING jobs and return IDs that need waiting."""
        non_terminal = {SyncJobStatus.PENDING, SyncJobStatus.RUNNING, SyncJobStatus.CANCELLING}
        syncs_to_wait: List[UUID] = []
        for sync_id in sync_ids:
            latest_job = await self._sync_job_repo.get_latest_by_sync_id(db, sync_id=sync_id)
            if not latest_job or latest_job.status not in non_terminal:
                continue
            if latest_job.status in (SyncJobStatus.PENDING, SyncJobStatus.RUNNING):
                try:
                    await self._temporal_workflow_service.cancel_sync_job_workflow(
                        str(latest_job.id), ctx
                    )
                    ctx.logger.info(f"Cancelled job {latest_job.id} before deletion")
                except Exception as e:
                    ctx.logger.warning(f"Failed to cancel job {latest_job.id}: {e}")
            syncs_to_wait.append(sync_id)
        return syncs_to_wait

    async def _wait_for_terminal(
        self,
        db: AsyncSession,
        syncs_to_wait: List[UUID],
        timeout_seconds: int,
        ctx: ApiContext,
    ) -> None:
        """Poll until all syncs reach a terminal state or timeout."""
        if not syncs_to_wait:
            return
        terminal = {SyncJobStatus.COMPLETED, SyncJobStatus.FAILED, SyncJobStatus.CANCELLED}
        elapsed = 0.0
        remaining = list(syncs_to_wait)
        while elapsed < timeout_seconds and remaining:
            await asyncio.sleep(1.0)
            elapsed += 1.0
            db.expire_all()
            still_waiting = []
            for sid in remaining:
                job = await self._sync_job_repo.get_latest_by_sync_id(db, sync_id=sid)
                if job and job.status not in terminal:
                    still_waiting.append(sid)
            remaining = still_waiting
        if remaining:
            ctx.logger.warning(
                f"{len(remaining)} sync(s) did not reach terminal state "
                f"within {timeout_seconds}s -- proceeding with deletion anyway"
            )

    async def _schedule_collection_cleanup(
        self,
        sync_ids: List[UUID],
        collection_id: UUID,
        organization_id: UUID,
        ctx: ApiContext,
    ) -> None:
        """Schedule a Temporal workflow for async Vespa/ARF cleanup."""
        if not sync_ids:
            return
        try:
            await self._temporal_workflow_service.start_cleanup_sync_data_workflow(
                sync_ids=[str(sid) for sid in sync_ids],
                collection_id=str(collection_id),
                organization_id=str(organization_id),
                ctx=ctx,
            )
        except Exception as e:
            ctx.logger.error(
                f"Failed to schedule async cleanup for collection {collection_id}: {e}. "
                f"Data may be orphaned in Vespa/ARF."
            )

    async def _validate_force_full_sync(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> None:
        """Raise 400 if force_full_sync is invalid for this sync."""
        cursor = await self._sync_cursor_repo.get_by_sync_id(db, sync_id, ctx)
        if not cursor or not cursor.cursor_data:
            raise HTTPException(
                status_code=400,
                detail=(
                    "force_full_sync can only be used with continuous syncs "
                    "(syncs with cursor data). This sync is non-continuous and "
                    "always performs full syncs by default."
                ),
            )
        ctx.logger.info(
            f"Force full sync requested for continuous sync {sync_id}. "
            "Will ignore cursor data and perform full sync with orphaned entity cleanup."
        )

    async def _resolve_connection(
        self, db: AsyncSession, source_conn, ctx: ApiContext
    ) -> schemas.Connection:
        """Resolve the Connection (not SourceConnection!) for a source connection."""
        if not source_conn.connection_id:
            raise ValueError(f"Source connection {source_conn.id} has no connection_id")
        conn = await self._connection_repo.get(db, source_conn.connection_id, ctx)
        if not conn:
            raise ValueError(f"Connection {source_conn.connection_id} not found")
        return schemas.Connection.model_validate(conn, from_attributes=True)

    def _resolve_cron(
        self,
        schedule_config: Optional[ScheduleConfig],
        source_entry: SourceRegistryEntry,
        ctx: ApiContext,
    ) -> Optional[str]:
        """Resolve cron schedule from config or source defaults.

        When schedule_config is provided:
          - cron is a string → use it
          - cron is None → caller explicitly wants no schedule
        When schedule_config is None → apply source-type defaults.
        """
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

    def _validate_cron_for_source(
        self,
        cron: str,
        source_entry: SourceRegistryEntry,
    ) -> None:
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
