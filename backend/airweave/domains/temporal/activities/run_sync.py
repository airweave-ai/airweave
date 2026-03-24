"""Run sync activity — pure execution with heartbeating and metrics.

State transitions (COMPLETED/FAILED/CANCELLED) are NOT handled here.
The workflow calls TransitionSyncJobActivity for those. RUNNING is
published by the orchestrator when sync work actually begins.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Optional
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError, ApplicationErrorCategory

from airweave import crud, schemas
from airweave.core.context import BaseContext
from airweave.core.exceptions import NotFoundException
from airweave.db.session import get_db_context
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.sync_pipeline.config import SyncConfig
from airweave.domains.syncs.protocols import SyncRepositoryProtocol, SyncServiceProtocol
from airweave.domains.temporal.activities.context import build_activity_context
from airweave.domains.temporal.activities.heartbeat import HeartbeatMonitor
from airweave.domains.temporal.exceptions import ORPHANED_SYNC_ERROR_TYPE, OrphanedSyncError
from airweave.domains.temporal.metrics import worker_metrics


@asynccontextmanager
async def _track_metrics(
    sync_job: schemas.SyncJob,
    sync: schemas.Sync,
    organization: schemas.Organization,
    collection: schemas.CollectionRecord,
    connection: schemas.Connection,
    force_full_sync: bool,
    ctx: BaseContext,
) -> AsyncIterator[None]:
    """Best-effort metrics tracking -- falls back to a no-op on failure."""
    ctx_mgr = worker_metrics.track_activity(
        activity_name="run_sync_activity",
        sync_job_id=sync_job.id,
        sync_id=sync.id,
        organization_id=organization.id,
        metadata={
            "connection_name": connection.name,
            "collection_name": collection.name,
            "force_full_sync": force_full_sync,
            "source_type": connection.short_name,
            "org_name": organization.name,
        },
    )
    entered = False
    try:
        await ctx_mgr.__aenter__()
        entered = True
    except Exception as e:
        ctx.logger.warning(f"Metrics tracking failed to start: {e}")
    try:
        yield
    finally:
        if entered:
            with suppress(Exception):
                await ctx_mgr.__aexit__(None, None, None)


@dataclass
class RunSyncActivity:
    """Execute a sync job with heartbeating and metrics.

    This activity is pure execution — it does NOT publish lifecycle events
    or update sync job status. The workflow handles state transitions via
    TransitionSyncJobActivity; RUNNING is published by the orchestrator.

    Dependencies:
        sync_service: Build orchestrator and run sync
        collection_repo: Fetch fresh collection data from DB
    """

    sync_service: SyncServiceProtocol
    sync_repo: SyncRepositoryProtocol
    collection_repo: CollectionRepositoryProtocol

    @activity.defn(name="run_sync_activity")
    async def run(
        self,
        sync_dict: Dict[str, Any],
        sync_job_dict: Dict[str, Any],
        collection_dict: Dict[str, Any],
        connection_dict: Dict[str, Any],
        ctx_dict: Dict[str, Any],
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
    ) -> None:
        """Execute a sync job. Raises on failure; returns None on success."""
        sync_job = schemas.SyncJob(**sync_job_dict)
        connection = schemas.Connection(**connection_dict)

        ctx = await build_activity_context(ctx_dict, sync_job_id=str(sync_job.id))
        organization = ctx.organization

        sync, collection = await self._resolve_from_db(sync_dict, collection_dict, ctx)

        ctx.logger.debug(f"Starting sync activity for job {sync_job.id}")

        async with _track_metrics(
            sync_job, sync, organization, collection, connection, force_full_sync, ctx
        ):
            await self._execute_with_heartbeat(
                sync, sync_job, collection, connection, ctx, access_token, force_full_sync
            )

        ctx.logger.info(f"Completed sync activity for job {sync_job.id}")

    # ------------------------------------------------------------------
    # DB resolution
    # ------------------------------------------------------------------

    async def _resolve_from_db(
        self,
        sync_dict: Dict[str, Any],
        collection_dict: Dict[str, Any],
        ctx: BaseContext,
    ) -> tuple[schemas.Sync, schemas.CollectionRecord]:
        """Fetch fresh sync and collection from the database."""
        sync_id = UUID(sync_dict["id"])
        collection_id = UUID(collection_dict["id"])

        async with get_db_context() as db:
            sync = await self.sync_repo.get(db=db, id=sync_id, ctx=ctx)
            if not sync:
                raise ValueError(f"Sync {sync_id} not found in database")

            collection_model = await self.collection_repo.get(db=db, id=collection_id, ctx=ctx)
            if not collection_model:
                raise ValueError(f"Collection {collection_id} not found in database")
            collection = schemas.CollectionRecord.model_validate(
                collection_model, from_attributes=True
            )

        return sync, collection

    # ------------------------------------------------------------------
    # Execution with heartbeat
    # ------------------------------------------------------------------

    async def _execute_with_heartbeat(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.CollectionRecord,
        connection: schemas.Connection,
        ctx: BaseContext,
        access_token: Optional[str],
        force_full_sync: bool,
    ) -> None:
        """Run the sync as a background task with a heartbeat monitor alongside."""
        sync_task = asyncio.create_task(
            self._run_sync(
                sync, sync_job, collection, connection, ctx, access_token, force_full_sync
            )
        )
        try:
            await HeartbeatMonitor(sync, sync_job, ctx).run(sync_task)
        except asyncio.CancelledError:
            await self._drain_task(ctx, sync_task)
            raise

    # ------------------------------------------------------------------
    # Sync execution
    # ------------------------------------------------------------------

    async def _run_sync(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.CollectionRecord,
        connection: schemas.Connection,
        ctx: BaseContext,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
    ) -> None:
        """Run the sync service. Converts orphaned-sync conditions to ApplicationError."""
        execution_config = await self._load_execution_config(sync_job, ctx)

        try:
            await self.sync_service.run(
                sync=sync,
                sync_job=sync_job,
                collection=collection,
                source_connection=connection,
                ctx=ctx,
                force_full_sync=force_full_sync,
                execution_config=execution_config,
                access_token=access_token,
            )
        except NotFoundException as e:
            if "Source connection record not found" in str(e) or "Connection not found" in str(e):
                orphaned = OrphanedSyncError(str(sync.id))
                ctx.logger.info(
                    f"Source connection for sync {sync.id} not found -- "
                    f"resource was likely deleted during execution"
                )
                raise ApplicationError(
                    str(orphaned),
                    orphaned.sync_id,
                    orphaned.reason,
                    type=ORPHANED_SYNC_ERROR_TYPE,
                    non_retryable=True,
                    category=ApplicationErrorCategory.BENIGN,
                ) from e
            raise

    async def _load_execution_config(
        self, sync_job: schemas.SyncJob, ctx: BaseContext
    ) -> SyncConfig | None:
        """Load execution config from DB, or None on failure."""
        try:
            async with get_db_context() as db:
                model = await crud.sync_job.get(db, id=sync_job.id, ctx=ctx)
                if model and model.sync_config:
                    return SyncConfig(**model.sync_config)
        except Exception as e:
            ctx.logger.warning(f"Failed to load execution config: {e}")
        return None

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    async def _drain_task(self, ctx: BaseContext, sync_task: asyncio.Task[Any]) -> None:
        """Cancel the sync task and wait for it to finish, heartbeating while waiting."""
        ctx.logger.info("Cancelling sync task")
        sync_task.cancel()
        while not sync_task.done():
            try:
                await asyncio.wait_for(sync_task, timeout=1)
            except asyncio.TimeoutError:
                activity.heartbeat({"phase": "cancelling"})
        with suppress(asyncio.CancelledError):
            await sync_task
