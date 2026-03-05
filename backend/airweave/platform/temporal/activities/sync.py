"""Temporal activities for sync operations.

Activity classes with explicit dependency injection.
Each class declares its dependencies in __init__, making them:
- Visible and documented
- Testable with fakes
- Wired at worker startup via container
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import traceback
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from temporalio import activity

from airweave import schemas
from airweave.core.context import BaseContext
from airweave.core.protocols import EventBus
from airweave.core.redis_client import redis_client
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol

# =============================================================================
# Run Sync Activity
# =============================================================================


@dataclass
class RunSyncActivity:
    """Execute a sync job.

    Dependencies:
        event_bus: Publish sync lifecycle events (RUNNING, COMPLETED, FAILED, CANCELLED)

    Inputs:
        sync_dict, sync_job_dict, collection_dict, connection_dict, ctx_dict
        access_token, force_full_sync

    Note: Currently accepts serialized dicts for backward compatibility with
    existing workflows. Future: migrate to IDs-only.
    """

    event_bus: EventBus
    dense_embedder: DenseEmbedderProtocol
    sparse_embedder: SparseEmbedderProtocol

    @activity.defn(name="run_sync_activity")
    async def run(  # noqa: C901
        self,
        sync_dict: Dict[str, Any],
        sync_job_dict: Dict[str, Any],
        collection_dict: Dict[str, Any],
        connection_dict: Dict[str, Any],
        ctx_dict: Dict[str, Any],
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
    ) -> None:
        """Activity to run a sync job.

        Args:
            sync_dict: The sync configuration as dict
            sync_job_dict: The sync job as dict
            collection_dict: The collection as dict
            connection_dict: The connection as dict (Connection schema, NOT SourceConnection)
            ctx_dict: The API context as dict
            access_token: Optional access token
            force_full_sync: If True, forces a full sync with orphaned entity deletion
        """
        # Import here to avoid Temporal sandboxing issues
        from airweave import crud, schemas
        from airweave.core.context import BaseContext
        from airweave.db.session import get_db_context
        from airweave.platform.temporal.worker_metrics import worker_metrics

        # Convert dicts back to Pydantic models
        sync_job = schemas.SyncJob(**sync_job_dict)
        connection = schemas.Connection(**connection_dict)

        organization = schemas.Organization(**ctx_dict["organization"])

        ctx = BaseContext(organization=organization)
        ctx.logger = ctx.logger.with_context(sync_job_id=str(sync_job.id))

        # Fetch fresh sync and collection from DB to avoid stale data
        # (Temporal schedules bake sync_dict at creation time, which can
        # contain outdated destination_connection_ids after migrations)
        sync_id = UUID(sync_dict["id"])
        collection_id = UUID(collection_dict["id"])
        async with get_db_context() as db:
            # Fetch sync with connections to get current destination_connection_ids
            try:
                sync = await crud.sync.get(db=db, id=sync_id, ctx=ctx, with_connections=True)
                if not sync.destination_connection_ids:
                    ctx.logger.warning(
                        f"Sync {sync_id} has no destination connections in DB. "
                        f"Falling back to workflow-provided sync_dict."
                    )
                    sync = schemas.Sync(**sync_dict)
                else:
                    ctx.logger.info(
                        f"Fetched fresh sync data from DB: {sync.id} "
                        f"(destinations={sync.destination_connection_ids})"
                    )
            except Exception as e:
                ctx.logger.warning(
                    f"Failed to fetch sync {sync_id} from DB: {e}. "
                    f"Falling back to workflow-provided sync_dict."
                )
                sync = schemas.Sync(**sync_dict)

            collection_model = await crud.collection.get(db=db, id=collection_id, ctx=ctx)
            if not collection_model:
                raise ValueError(f"Collection {collection_id} not found in database")

            collection = schemas.CollectionRecord.model_validate(
                collection_model, from_attributes=True
            )
            ctx.logger.info(f"Fetched fresh collection data from DB: {collection.readable_id}")

            # Fetch the SourceConnection to get its user-facing ID for webhook events.
            # sync.source_connection_id is the internal Connection.id, NOT the
            # SourceConnection.id that users see in the API and webhook payloads.
            source_connection_id = sync.source_connection_id  # fallback: internal ID
            try:
                source_conn = await crud.source_connection.get_by_sync_id(
                    db=db, sync_id=sync_id, ctx=ctx
                )
                if source_conn:
                    source_connection_id = source_conn.id
                    ctx.logger.info(
                        f"Resolved SourceConnection.id={source_connection_id} "
                        f"(internal Connection.id={sync.source_connection_id})"
                    )
                else:
                    ctx.logger.warning(
                        f"No SourceConnection found for sync {sync_id}. "
                        f"Falling back to sync.source_connection_id={sync.source_connection_id}"
                    )
            except Exception as e:
                ctx.logger.warning(
                    f"Failed to fetch SourceConnection for sync {sync_id}: {e}. "
                    f"Falling back to sync.source_connection_id={sync.source_connection_id}"
                )

        ctx.logger.debug(f"\n\nStarting sync activity for job {sync_job.id}\n\n")

        # Track this activity in worker metrics (fail-safe: never crash sync)
        tracking_context = None
        try:
            tracking_context = worker_metrics.track_activity(
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
            await tracking_context.__aenter__()
        except Exception as e:
            ctx.logger.warning(f"Failed to register activity in metrics: {e}")
            tracking_context = None

        try:
            # Start the sync task
            sync_task = asyncio.create_task(
                self._run_sync_task(
                    sync,
                    sync_job,
                    collection,
                    connection,
                    ctx,
                    access_token,
                    force_full_sync,
                )
            )

            # Publish RUNNING event
            from airweave.core.events.sync import SyncLifecycleEvent

            await self.event_bus.publish(
                SyncLifecycleEvent.running(
                    organization_id=organization.id,
                    source_connection_id=source_connection_id,
                    sync_job_id=sync_job.id,
                    sync_id=sync.id,
                    collection_id=collection.id,
                    source_type=connection.short_name,
                    collection_name=collection.name,
                    collection_readable_id=collection.readable_id,
                )
            )

            # Track timing for stack trace dumps
            heartbeat_start_time = time.time()
            last_stack_dump_time = heartbeat_start_time
            stack_dump_interval = 600  # 10 minutes

            # Stall detection via Redis progress snapshot
            last_redis_check_time = heartbeat_start_time
            redis_check_interval = 30  # check every 30 seconds
            last_known_timestamp = None
            stall_start_time = None
            stall_dump_emitted = False
            stall_threshold = 300  # 5 minutes without progress

            def _emit_stack_dump(reason: str, elapsed_s: int):
                """Collect and emit a chunked stack trace dump."""
                traces = []
                for thread_id, frame in sys._current_frames().items():
                    traces.append(f"\n=== Thread {thread_id} ===")
                    traces.append("".join(traceback.format_stack(frame)))
                all_tasks = asyncio.all_tasks()
                traces.append(f"\n=== Async Tasks ({len(all_tasks)} total) ===")
                for task in all_tasks:
                    if not task.done():
                        task_name = task.get_name()
                        coro = task.get_coro()
                        if hasattr(coro, "cr_frame") and coro.cr_frame:
                            frame = coro.cr_frame
                            traces.append(f"\nTask: {task_name}")
                            loc = f"{frame.f_code.co_filename}:{frame.f_lineno}"
                            traces.append(f"  at {loc} in {frame.f_code.co_name}")

                thread_parts = []
                async_parts = []
                in_async = False
                for trace in traces:
                    if "=== Async Tasks" in trace:
                        in_async = True
                    (async_parts if in_async else thread_parts).append(trace)

                base_extra = {
                    "elapsed_seconds": elapsed_s,
                    "sync_id": str(sync.id),
                    "sync_job_id": str(sync_job.id),
                }

                ctx.logger.debug(
                    f"[STACK_TRACE_DUMP] sync={sync.id} "
                    f"sync_job={sync_job.id} elapsed={elapsed_s}s "
                    f"reason={reason} part=threads",
                    extra={**base_extra, "stack_traces": "".join(thread_parts)},
                )

                async_str = "".join(async_parts)
                chunk_size = 12000
                chunk_idx = 0
                for i in range(0, max(len(async_str), 1), chunk_size):
                    chunk_idx += 1
                    ctx.logger.debug(
                        f"[STACK_TRACE_DUMP] sync={sync.id} "
                        f"sync_job={sync_job.id} elapsed={elapsed_s}s "
                        f"reason={reason} part=async_tasks chunk={chunk_idx}",
                        extra={
                            **base_extra,
                            "stack_traces": async_str[i : i + chunk_size],
                            "chunk": chunk_idx,
                        },
                    )

            try:
                while True:
                    done, _ = await asyncio.wait({sync_task}, timeout=1)
                    if sync_task in done:
                        await sync_task
                        break

                    current_time = time.time()
                    elapsed_seconds = int(current_time - heartbeat_start_time)

                    # Stall detection: read Redis progress snapshot periodically
                    if (current_time - last_redis_check_time) >= redis_check_interval:
                        last_redis_check_time = current_time
                        try:
                            snapshot_key = f"sync_progress_snapshot:{sync_job.id}"
                            snapshot_raw = await redis_client.client.get(snapshot_key)
                            if snapshot_raw:
                                snapshot = json.loads(snapshot_raw)
                                current_timestamp = snapshot.get("last_update_timestamp")

                                if current_timestamp != last_known_timestamp:
                                    last_known_timestamp = current_timestamp
                                    stall_start_time = None
                                    stall_dump_emitted = False
                                elif stall_start_time is None:
                                    stall_start_time = current_time
                        except Exception:
                            pass

                    # Emit stall dump if no progress for 5 minutes
                    if (
                        stall_start_time is not None
                        and not stall_dump_emitted
                        and (current_time - stall_start_time) >= stall_threshold
                    ):
                        stall_seconds = int(current_time - stall_start_time)
                        ctx.logger.warning(
                            f"[STALL_DETECTED] sync={sync.id} "
                            f"sync_job={sync_job.id} "
                            f"no entity progress for {stall_seconds}s"
                        )
                        _emit_stack_dump("stall", elapsed_seconds)
                        stall_dump_emitted = True

                    # Regular periodic stack trace dump (every 10 min after 10 min)
                    if (
                        elapsed_seconds > 600
                        and (current_time - last_stack_dump_time) >= stack_dump_interval
                    ):
                        _emit_stack_dump("periodic", elapsed_seconds)
                        last_stack_dump_time = current_time

                    ctx.logger.debug("HEARTBEAT: Sync in progress")
                    activity.heartbeat("Sync in progress")

                # Publish COMPLETED event
                await self.event_bus.publish(
                    SyncLifecycleEvent.completed(
                        organization_id=organization.id,
                        source_connection_id=source_connection_id,
                        sync_job_id=sync_job.id,
                        sync_id=sync.id,
                        collection_id=collection.id,
                        source_type=connection.short_name,
                        collection_name=collection.name,
                        collection_readable_id=collection.readable_id,
                    )
                )
                ctx.logger.info(f"\n\nCompleted sync activity for job {sync_job.id}\n\n")

            except asyncio.CancelledError:
                await self._handle_cancellation(
                    sync,
                    sync_job,
                    collection,
                    connection,
                    organization,
                    ctx,
                    sync_task,
                    source_connection_id,
                )
                raise

            except Exception as e:
                ctx.logger.error(f"Failed sync activity for job {sync_job.id}: {e}")
                await self.event_bus.publish(
                    SyncLifecycleEvent.failed(
                        organization_id=organization.id,
                        source_connection_id=source_connection_id,
                        sync_job_id=sync_job.id,
                        sync_id=sync.id,
                        collection_id=collection.id,
                        source_type=connection.short_name,
                        collection_name=collection.name,
                        collection_readable_id=collection.readable_id,
                        error=str(e),
                    )
                )
                raise

        finally:
            # Clean up metrics tracking (fail-safe)
            if tracking_context:
                try:
                    await tracking_context.__aexit__(None, None, None)
                except Exception as cleanup_err:
                    ctx.logger.warning(f"Failed to cleanup metrics tracking: {cleanup_err}")

    async def _run_sync_task(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.Collection,
        connection: schemas.Connection,
        ctx: BaseContext,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
    ):
        """Run the actual sync service."""
        from airweave import crud
        from airweave.core.exceptions import NotFoundException
        from airweave.core.sync_service import sync_service
        from airweave.db.session import get_db_context
        from airweave.platform.sync.config import SyncConfig

        # Refetch sync_job from DB to get sync_config
        execution_config = None
        try:
            async with get_db_context() as db:
                sync_job_model = await crud.sync_job.get(db, id=sync_job.id, ctx=ctx)
                if sync_job_model and sync_job_model.sync_config:
                    execution_config = SyncConfig(**sync_job_model.sync_config)
                    ctx.logger.info(
                        f"Loaded execution config from DB: {sync_job_model.sync_config}"
                    )
        except Exception as e:
            ctx.logger.warning(f"Failed to load execution config from DB: {e}")

        try:
            return await sync_service.run(
                sync=sync,
                sync_job=sync_job,
                collection=collection,
                source_connection=connection,
                ctx=ctx,
                access_token=access_token,
                force_full_sync=force_full_sync,
                execution_config=execution_config,
                dense_embedder=self.dense_embedder,
                sparse_embedder=self.sparse_embedder,
            )
        except NotFoundException as e:
            if "Source connection record not found" in str(e) or "Connection not found" in str(e):
                ctx.logger.info(
                    f"🧹 Source connection for sync {sync.id} not found. "
                    f"Resource was likely deleted during workflow execution."
                )
                raise Exception("ORPHANED_SYNC: Source connection record not found") from e
            raise

    async def _handle_cancellation(
        self,
        sync,
        sync_job,
        collection,
        connection,
        organization,
        ctx,
        sync_task,
        source_connection_id=None,
    ):
        """Handle activity cancellation."""
        from airweave.core.datetime_utils import utc_now_naive
        from airweave.core.shared_models import SyncJobStatus
        from airweave.core.sync_job_service import sync_job_service

        ctx.logger.info(f"\n\n[ACTIVITY] Sync activity cancelled for job {sync_job.id}\n\n")

        # Update job status to CANCELLED
        try:
            await sync_job_service.update_status(
                sync_job_id=sync_job.id,
                status=SyncJobStatus.CANCELLED,
                ctx=ctx,
                error="Workflow was cancelled",
                failed_at=utc_now_naive(),
            )
            ctx.logger.debug(f"\n\n[ACTIVITY] Updated job {sync_job.id} to CANCELLED\n\n")

            from airweave.core.events.sync import SyncLifecycleEvent

            await self.event_bus.publish(
                SyncLifecycleEvent.cancelled(
                    organization_id=organization.id,
                    source_connection_id=source_connection_id or sync.source_connection_id,
                    sync_job_id=sync_job.id,
                    sync_id=sync.id,
                    collection_id=collection.id,
                    source_type=connection.short_name,
                    collection_name=collection.name,
                    collection_readable_id=collection.readable_id,
                )
            )
        except Exception as status_err:
            ctx.logger.error(f"Failed to update job {sync_job.id} to CANCELLED: {status_err}")

        # Cancel the internal sync task
        sync_task.cancel()
        while not sync_task.done():
            try:
                await asyncio.wait_for(sync_task, timeout=1)
            except asyncio.TimeoutError:
                activity.heartbeat("Cancelling sync...")
        with suppress(asyncio.CancelledError):
            await sync_task


# =============================================================================
# Mark Sync Job Cancelled Activity
# =============================================================================


@dataclass
class MarkSyncJobCancelledActivity:
    """Mark a sync job as CANCELLED.

    Dependencies: None (uses internal services)

    Used when workflow cancels before activity starts.
    """

    @activity.defn(name="mark_sync_job_cancelled_activity")
    async def run(
        self,
        sync_job_id: str,
        ctx_dict: Dict[str, Any],
        reason: Optional[str] = None,
        when_iso: Optional[str] = None,
    ) -> None:
        """Mark a sync job as CANCELLED.

        Args:
            sync_job_id: The sync job ID (str UUID)
            ctx_dict: Serialized ApiContext dict
            reason: Optional cancellation reason
            when_iso: Optional ISO timestamp for failed_at
        """
        from airweave import schemas
        from airweave.core.context import BaseContext
        from airweave.core.shared_models import SyncJobStatus
        from airweave.core.sync_job_service import sync_job_service

        organization = schemas.Organization(**ctx_dict["organization"])

        ctx = BaseContext(organization=organization)
        ctx.logger = ctx.logger.with_context(sync_job_id=sync_job_id)

        failed_at = None
        if when_iso:
            try:
                failed_at = datetime.fromisoformat(when_iso)
            except Exception:
                failed_at = None

        ctx.logger.debug(
            f"[WORKFLOW] Marking sync job {sync_job_id} as CANCELLED (pre-activity): {reason or ''}"
        )

        try:
            await sync_job_service.update_status(
                sync_job_id=UUID(sync_job_id),
                status=SyncJobStatus.CANCELLED,
                ctx=ctx,
                error=reason,
                failed_at=failed_at,
            )
            ctx.logger.debug(f"[WORKFLOW] Updated job {sync_job_id} to CANCELLED")
        except Exception as e:
            ctx.logger.error(f"Failed to update job {sync_job_id} to CANCELLED: {e}")
            raise


# =============================================================================
# Create Sync Job Activity
# =============================================================================


@dataclass
class CreateSyncJobActivity:
    """Create a new sync job record.

    Dependencies:
        event_bus: Publish PENDING event when job is created

    Returns sync job dict or {"_orphaned": True} if sync was deleted.
    """

    event_bus: "EventBus"

    @activity.defn(name="create_sync_job_activity")
    async def run(
        self,
        sync_id: str,
        ctx_dict: Dict[str, Any],
        force_full_sync: bool = False,
    ) -> Dict[str, Any]:
        """Create a new sync job for the given sync.

        Args:
            sync_id: The sync ID to create a job for
            ctx_dict: The API context as dict
            force_full_sync: If True (daily cleanup), wait for running jobs to complete

        Returns:
            The created sync job as a dict, or {"_orphaned": True} if sync was deleted

        Raises:
            Exception: If a sync job is already running and force_full_sync is False
        """
        from airweave import crud, schemas
        from airweave.core.context import BaseContext
        from airweave.core.exceptions import NotFoundException
        from airweave.core.shared_models import SyncJobStatus
        from airweave.db.session import get_db_context

        organization = schemas.Organization(**ctx_dict["organization"])

        ctx = BaseContext(organization=organization)
        ctx.logger = ctx.logger.with_context(sync_id=sync_id)

        ctx.logger.info(f"Creating sync job for sync {sync_id} (force_full_sync={force_full_sync})")

        async with get_db_context() as db:
            # Check if the sync still exists
            try:
                _ = await crud.sync.get(db=db, id=UUID(sync_id), ctx=ctx, with_connections=False)
            except NotFoundException as e:
                ctx.logger.info(
                    f"🧹 Could not verify sync {sync_id} exists: {e}. "
                    f"Marking as orphaned to trigger cleanup."
                )
                return {"_orphaned": True, "sync_id": sync_id, "reason": f"Sync lookup error: {e}"}

            # Check for running jobs
            running_jobs = await crud.sync_job.get_all_by_sync_id(
                db=db,
                sync_id=UUID(sync_id),
                status=[
                    SyncJobStatus.PENDING.value,
                    SyncJobStatus.RUNNING.value,
                    SyncJobStatus.CANCELLING.value,
                ],
            )

            if running_jobs:
                if force_full_sync:
                    await self._wait_for_running_jobs(
                        db, sync_id, ctx, running_jobs, SyncJobStatus, crud
                    )
                else:
                    ctx.logger.warning(
                        f"Sync {sync_id} already has {len(running_jobs)} running jobs. "
                        f"Skipping new job creation."
                    )
                    raise Exception(
                        f"Sync {sync_id} already has a running job. "
                        f"Skipping this scheduled run to avoid conflicts."
                    )

            # Create the new sync job
            sync_job_in = schemas.SyncJobCreate(sync_id=UUID(sync_id))
            sync_job = await crud.sync_job.create(db=db, obj_in=sync_job_in, ctx=ctx)
            sync_job_id = sync_job.id

            await db.commit()
            await db.refresh(sync_job)

            ctx.logger.info(f"Created sync job {sync_job_id} for sync {sync_id}")

            # Publish PENDING lifecycle event
            await self._publish_pending_event(db, sync_id, organization, sync_job, crud, ctx)

            sync_job_schema = schemas.SyncJob.model_validate(sync_job)
            return sync_job_schema.model_dump(mode="json")

    async def _wait_for_running_jobs(self, db, sync_id, ctx, running_jobs, SyncJobStatus, crud):
        """Wait for running jobs to complete before daily cleanup."""
        from airweave.db.session import get_db_context

        ctx.logger.info(
            f"🔄 Daily cleanup sync for {sync_id}: "
            f"Found {len(running_jobs)} running job(s). "
            f"Waiting for them to complete before starting cleanup..."
        )

        max_wait_time = 60 * 60  # 1 hour max wait
        wait_interval = 30
        total_waited = 0

        while total_waited < max_wait_time:
            activity.heartbeat(f"Waiting for running jobs to complete ({total_waited}s)")
            await asyncio.sleep(wait_interval)
            total_waited += wait_interval

            async with get_db_context() as check_db:
                still_running = await crud.sync_job.get_all_by_sync_id(
                    db=check_db,
                    sync_id=UUID(sync_id),
                    status=[
                        SyncJobStatus.PENDING.value,
                        SyncJobStatus.RUNNING.value,
                        SyncJobStatus.CANCELLING.value,
                    ],
                )

                if not still_running:
                    ctx.logger.info(
                        f"✅ Running jobs completed. Proceeding with cleanup sync for {sync_id}"
                    )
                    return

        ctx.logger.error(
            f"❌ Timeout waiting for running jobs to complete for sync {sync_id}. "
            f"Skipping cleanup sync."
        )
        raise Exception(f"Timeout waiting for running jobs to complete after {max_wait_time}s")

    async def _publish_pending_event(self, db, sync_id, organization, sync_job, crud, ctx):
        """Publish PENDING lifecycle event."""
        from airweave.core.events.sync import SyncLifecycleEvent

        try:
            source_conn = await crud.source_connection.get_by_sync_id(
                db=db, sync_id=UUID(sync_id), ctx=ctx
            )
            if source_conn:
                connection = await crud.connection.get(db=db, id=source_conn.connection_id, ctx=ctx)
                collection = await crud.collection.get(db=db, id=source_conn.collection_id, ctx=ctx)
                if connection and collection:
                    await self.event_bus.publish(
                        SyncLifecycleEvent.pending(
                            organization_id=organization.id,
                            source_connection_id=source_conn.id,
                            sync_job_id=sync_job.id,
                            sync_id=UUID(sync_id),
                            collection_id=collection.id,
                            source_type=connection.short_name,
                            collection_name=collection.name,
                            collection_readable_id=collection.readable_id,
                        )
                    )
        except Exception as event_err:
            ctx.logger.warning(f"Failed to publish pending event: {event_err}")


# =============================================================================
# Cleanup Stuck Sync Jobs Activity
# =============================================================================


@dataclass
class CleanupStuckSyncJobsActivity:
    """Clean up sync jobs stuck in transitional states.

    Dependencies: None (uses internal services)

    Detects and cancels:
    - CANCELLING/PENDING jobs stuck for > 3 minutes
    - RUNNING jobs stuck for > 10 minutes with no entity updates
    """

    @activity.defn(name="cleanup_stuck_sync_jobs_activity")
    async def run(self) -> None:
        """Run the cleanup activity."""
        from datetime import timedelta

        from airweave import crud
        from airweave.core.datetime_utils import utc_now_naive
        from airweave.core.logging import LoggerConfigurator
        from airweave.core.redis_client import redis_client
        from airweave.core.shared_models import SyncJobStatus
        from airweave.db.session import get_db_context

        logger = LoggerConfigurator.configure_logger(
            "airweave.temporal.cleanup",
            dimensions={"activity": "cleanup_stuck_sync_jobs"},
        )

        logger.info("Starting cleanup of stuck sync jobs...")

        now = utc_now_naive()
        cancelling_pending_cutoff = now - timedelta(minutes=3)
        running_cutoff = now - timedelta(minutes=15)

        try:
            async with get_db_context() as db:
                # Query CANCELLING/PENDING jobs stuck for > 3 minutes
                cancelling_pending_jobs = await crud.sync_job.get_stuck_jobs_by_status(
                    db=db,
                    status=[SyncJobStatus.CANCELLING.value, SyncJobStatus.PENDING.value],
                    modified_before=cancelling_pending_cutoff,
                )
                logger.info(
                    f"Found {len(cancelling_pending_jobs)} CANCELLING/PENDING jobs "
                    f"stuck for > 3 minutes"
                )

                # Query RUNNING jobs > 15 minutes old
                running_jobs = await crud.sync_job.get_stuck_jobs_by_status(
                    db=db,
                    status=[SyncJobStatus.RUNNING.value],
                    started_before=running_cutoff,
                )
                logger.info(
                    f"Found {len(running_jobs)} RUNNING jobs started >15min ago "
                    f"(will check activity)"
                )

                # Filter to jobs with no recent activity
                stuck_running_jobs = []
                for job in running_jobs:
                    if await self._is_running_job_stuck(
                        job, running_cutoff, db, redis_client, crud, logger
                    ):
                        stuck_running_jobs.append(job)
                logger.info(
                    f"Found {len(stuck_running_jobs)} RUNNING jobs "
                    f"with no activity in last 15 minutes"
                )

                # Combine all stuck jobs
                all_stuck_jobs = cancelling_pending_jobs + stuck_running_jobs
                stuck_job_count = len(all_stuck_jobs)

                if stuck_job_count == 0:
                    logger.info("No stuck jobs found. Cleanup complete.")
                    return

                logger.info(f"Processing {stuck_job_count} stuck sync jobs...")

                # Process each stuck job
                cancelled_count = 0
                failed_count = 0
                for job in all_stuck_jobs:
                    success = await self._cancel_stuck_job(job, now, db, crud, logger)
                    if success:
                        cancelled_count += 1
                    else:
                        failed_count += 1

                logger.info(
                    f"Cleanup complete. Processed {stuck_job_count} stuck jobs: "
                    f"{cancelled_count} cancelled, {failed_count} failed"
                )

        except Exception as e:
            logger.error(f"Error during cleanup activity: {e}", exc_info=True)
            raise

    async def _is_running_job_stuck(
        self, job, running_cutoff, db, redis_client, crud, logger
    ) -> bool:
        """Check if a running job is stuck (no recent activity)."""
        import json
        from datetime import datetime

        # Skip ARF-only backfills
        if job.sync_config:
            handlers = job.sync_config.get("handlers", {})
            is_arf_only = not handlers.get("enable_postgres_handler", True)
            if is_arf_only:
                logger.debug(f"Skipping ARF-only job {job.id} from stuck detection")
                return False

        job_id_str = str(job.id)
        snapshot_key = f"sync_progress_snapshot:{job_id_str}"

        try:
            snapshot_json = await redis_client.client.get(snapshot_key)

            if not snapshot_json:
                logger.debug(f"No snapshot for job {job_id_str} - skipping")
                return False

            snapshot = json.loads(snapshot_json)
            last_update_str = snapshot.get("last_update_timestamp")

            if not last_update_str:
                latest_entity_time = await crud.entity.get_latest_entity_time_for_job(
                    db=db, sync_job_id=job.id
                )
                return latest_entity_time is None or latest_entity_time < running_cutoff

            last_update = datetime.fromisoformat(last_update_str)
            if last_update.tzinfo is not None:
                last_update = last_update.replace(tzinfo=None)

            if last_update < running_cutoff:
                total_ops = sum(
                    [
                        snapshot.get("inserted", 0),
                        snapshot.get("updated", 0),
                        snapshot.get("deleted", 0),
                        snapshot.get("kept", 0),
                        snapshot.get("skipped", 0),
                    ]
                )
                logger.info(
                    f"Job {job_id_str} last activity at {last_update} "
                    f"({total_ops} total ops) - marking as stuck"
                )
                return True

            logger.debug(f"Job {job_id_str} active at {last_update} - healthy")
            return False

        except Exception as e:
            logger.warning(f"Error checking job {job_id_str}: {e}, falling back to DB check")
            latest_entity_time = await crud.entity.get_latest_entity_time_for_job(
                db=db, sync_job_id=job.id
            )
            return latest_entity_time is None or latest_entity_time < running_cutoff

    async def _cancel_stuck_job(self, job, now, db, crud, logger) -> bool:
        """Cancel a single stuck job via Temporal and update database."""
        from airweave import schemas
        from airweave.core.context import BaseContext
        from airweave.core.shared_models import SyncJobStatus
        from airweave.core.sync_job_service import sync_job_service
        from airweave.core.temporal_service import temporal_service

        job_id = str(job.id)
        sync_id = str(job.sync_id)
        org_id = str(job.organization_id)

        logger.info(
            f"Attempting to cancel stuck job {job_id} "
            f"(status: {job.status}, sync: {sync_id}, org: {org_id})"
        )

        try:
            organization = await crud.organization.get(
                db=db,
                id=job.organization_id,
                skip_access_validation=True,
            )
        except Exception as e:
            logger.error(f"Failed to fetch organization {org_id} for job {job_id}: {e}")
            return False

        ctx = BaseContext(
            organization=schemas.Organization.model_validate(organization),
            logger=logger,
        )

        try:
            cancel_success = await temporal_service.cancel_sync_job_workflow(job_id, ctx)

            if cancel_success:
                logger.info(f"Successfully requested Temporal cancellation for job {job_id}")
                await asyncio.sleep(2)

            await sync_job_service.update_status(
                sync_job_id=UUID(job_id),
                status=SyncJobStatus.CANCELLED,
                ctx=ctx,
                error="Cancelled by cleanup job (stuck in transitional state)",
                failed_at=now,
            )

            logger.info(f"Successfully cancelled stuck job {job_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel stuck job {job_id}: {e}", exc_info=True)
            return False
