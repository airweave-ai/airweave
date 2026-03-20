"""Temporal activity for running a sync job."""

from __future__ import annotations

import asyncio
import json
import sys
import time
import traceback
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

from temporalio import activity

from airweave import schemas
from airweave.core.context import BaseContext
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.events.sync import SyncLifecycleEvent
from airweave.core.exceptions import NotFoundException
from airweave.core.protocols import EventBus
from airweave.core.redis_client import redis_client
from airweave.core.shared_models import SyncJobStatus
from airweave.db.session import get_db_context
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.source_connections.protocols import SourceConnectionRepositoryProtocol
from airweave.domains.syncs.protocols import (
    SyncJobRepositoryProtocol,
    SyncJobServiceProtocol,
    SyncRepositoryProtocol,
    SyncServiceProtocol,
)
from airweave.platform.sync.config import SyncConfig
from airweave.platform.temporal.worker_metrics import worker_metrics

if TYPE_CHECKING:
    pass


@dataclass
class RunSyncActivity:
    """Execute a sync job."""

    event_bus: EventBus
    sync_service: SyncServiceProtocol
    sync_job_service: SyncJobServiceProtocol
    sync_repo: SyncRepositoryProtocol
    sync_job_repo: SyncJobRepositoryProtocol
    sc_repo: SourceConnectionRepositoryProtocol
    collection_repo: CollectionRepositoryProtocol

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
        """Execute the sync via SyncService with heartbeat monitoring."""
        sync_job = schemas.SyncJob(**sync_job_dict)
        connection = schemas.Connection(**connection_dict)
        organization = schemas.Organization(**ctx_dict["organization"])

        ctx = BaseContext(organization=organization)
        ctx.logger = ctx.logger.with_context(sync_job_id=str(sync_job.id))

        sync_id = UUID(sync_dict["id"])
        collection_id = UUID(collection_dict["id"])

        async with get_db_context() as db:
            try:
                sync = await self.sync_repo.get(db=db, id=sync_id, ctx=ctx)  # type: ignore[arg-type]
                if not sync or not sync.destination_connection_ids:
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

            collection_model = await self.collection_repo.get(
                db=db,
                id=collection_id,
                ctx=ctx,  # type: ignore[arg-type]
            )
            if not collection_model:
                raise ValueError(f"Collection {collection_id} not found in database")

            collection = schemas.CollectionRecord.model_validate(
                collection_model, from_attributes=True
            )
            ctx.logger.info(f"Fetched fresh collection data from DB: {collection.readable_id}")

            source_connection_id: UUID = sync.source_connection_id
            try:
                source_conn = await self.sc_repo.get_by_sync_id(
                    db=db,
                    sync_id=sync_id,
                    ctx=ctx,  # type: ignore[arg-type]
                )
                if source_conn:
                    source_connection_id = UUID(str(source_conn.id))
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

            try:
                await self._heartbeat_loop(sync, sync_job, ctx, sync_task)

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
            if tracking_context:
                try:
                    await tracking_context.__aexit__(None, None, None)
                except Exception as cleanup_err:
                    ctx.logger.warning(f"Failed to cleanup metrics tracking: {cleanup_err}")

    async def _run_sync_task(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.CollectionRecord,
        connection: schemas.Connection,
        ctx: BaseContext,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
    ) -> schemas.Sync:
        execution_config = None
        try:
            async with get_db_context() as db:
                sync_job_model = await self.sync_job_repo.get(
                    db,
                    id=sync_job.id,
                    ctx=ctx,  # type: ignore[arg-type]
                )
                if sync_job_model and sync_job_model.sync_config:
                    execution_config = SyncConfig(**sync_job_model.sync_config)
                    ctx.logger.info(
                        f"Loaded execution config from DB: {sync_job_model.sync_config}"
                    )
        except Exception as e:
            ctx.logger.warning(f"Failed to load execution config from DB: {e}")

        try:
            return await self.sync_service.run(
                sync=sync,
                sync_job=sync_job,
                collection=collection,
                source_connection=connection,
                ctx=ctx,  # type: ignore[arg-type]
                access_token=access_token,
                force_full_sync=force_full_sync,
                execution_config=execution_config,
            )
        except NotFoundException as e:
            if "Source connection record not found" in str(e) or "Connection not found" in str(e):
                ctx.logger.info(
                    f"🧹 Source connection for sync {sync.id} not found. "
                    f"Resource was likely deleted during workflow execution."
                )
                raise Exception("ORPHANED_SYNC: Source connection record not found") from e
            raise

    async def _heartbeat_loop(  # noqa: C901
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        ctx: BaseContext,
        sync_task: asyncio.Task[Any],
    ) -> None:
        heartbeat_start_time = time.time()
        last_stack_dump_time = heartbeat_start_time
        stack_dump_interval = 600

        last_redis_check_time = heartbeat_start_time
        redis_check_interval = 30
        last_known_timestamp: Optional[str] = None
        last_snapshot: dict[str, Any] = {}
        stall_start_time: Optional[float] = None
        stall_dump_emitted = False
        stall_threshold = 300

        while True:
            done, _ = await asyncio.wait({sync_task}, timeout=1)
            if sync_task in done:
                await sync_task
                break

            current_time = time.time()
            elapsed_seconds = int(current_time - heartbeat_start_time)

            if (current_time - last_redis_check_time) >= redis_check_interval:
                last_redis_check_time = current_time
                try:
                    snapshot_key = f"sync_progress_snapshot:{sync_job.id}"
                    snapshot_raw = await redis_client.client.get(snapshot_key)
                    if snapshot_raw:
                        last_snapshot = json.loads(snapshot_raw)
                        current_timestamp = last_snapshot.get("last_update_timestamp")

                        if current_timestamp != last_known_timestamp:
                            last_known_timestamp = current_timestamp
                            stall_start_time = None
                            stall_dump_emitted = False
                        elif stall_start_time is None:
                            stall_start_time = current_time
                except Exception:
                    pass

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
                self._emit_stack_dump(sync, sync_job, ctx, "stall", elapsed_seconds)
                stall_dump_emitted = True

            if (
                elapsed_seconds > 600
                and (current_time - last_stack_dump_time) >= stack_dump_interval
            ):
                self._emit_stack_dump(sync, sync_job, ctx, "periodic", elapsed_seconds)
                last_stack_dump_time = current_time

            heartbeat_data: dict[str, Any] = {
                "phase": "syncing",
                "elapsed_s": elapsed_seconds,
            }
            if last_known_timestamp:
                heartbeat_data["last_progress_at"] = last_known_timestamp
            if last_snapshot:
                heartbeat_data["inserted"] = last_snapshot.get("inserted", 0)
                heartbeat_data["updated"] = last_snapshot.get("updated", 0)
                heartbeat_data["deleted"] = last_snapshot.get("deleted", 0)
                heartbeat_data["kept"] = last_snapshot.get("kept", 0)
            if stall_start_time is not None:
                heartbeat_data["stall_s"] = int(current_time - stall_start_time)

            ctx.logger.debug("HEARTBEAT: Sync in progress")
            activity.heartbeat(heartbeat_data)

    @staticmethod
    def _emit_stack_dump(
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        ctx: BaseContext,
        reason: str,
        elapsed_s: int,
    ) -> None:
        traces: List[str] = []
        for thread_id, frame in sys._current_frames().items():
            traces.append(f"\n=== Thread {thread_id} ===")
            traces.append("".join(traceback.format_stack(frame)))
        all_tasks = asyncio.all_tasks()
        traces.append(f"\n=== Async Tasks ({len(all_tasks)} total) ===")
        for task in all_tasks:
            if not task.done():
                task_name = task.get_name()
                coro = task.get_coro()
                if coro is not None and hasattr(coro, "cr_frame") and coro.cr_frame:
                    cr_frame = coro.cr_frame
                    traces.append(f"\nTask: {task_name}")
                    loc = f"{cr_frame.f_code.co_filename}:{cr_frame.f_lineno}"
                    traces.append(f"  at {loc} in {cr_frame.f_code.co_name}")

        thread_parts: List[str] = []
        async_parts: List[str] = []
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

    async def _handle_cancellation(
        self,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.CollectionRecord,
        connection: schemas.Connection,
        organization: schemas.Organization,
        ctx: BaseContext,
        sync_task: asyncio.Task[Any],
        source_connection_id: Optional[UUID] = None,
    ) -> None:
        ctx.logger.info(f"\n\n[ACTIVITY] Sync activity cancelled for job {sync_job.id}\n\n")

        try:
            await self.sync_job_service.update_status(
                sync_job_id=sync_job.id,
                status=SyncJobStatus.CANCELLED,
                ctx=ctx,  # type: ignore[arg-type]
                error="Workflow was cancelled",
                failed_at=utc_now_naive(),
            )
            ctx.logger.debug(f"\n\n[ACTIVITY] Updated job {sync_job.id} to CANCELLED\n\n")

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

        sync_task.cancel()
        while not sync_task.done():
            try:
                await asyncio.wait_for(sync_task, timeout=1)
            except asyncio.TimeoutError:
                activity.heartbeat({"phase": "cancelling"})
        with suppress(asyncio.CancelledError):
            await sync_task
