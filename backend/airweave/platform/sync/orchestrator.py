"""Module for data synchronization with TRUE batching + toggleable batching."""

import asyncio
from typing import Optional

from airweave import schemas
from airweave.analytics import business_events
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.exceptions import PaymentRequiredException, UsageLimitExceededException
from airweave.core.guard_rail_service import ActionType
from airweave.core.shared_models import SyncJobStatus
from airweave.core.sync_cursor_service import sync_cursor_service
from airweave.core.sync_job_service import sync_job_service
from airweave.db.session import get_db_context
from airweave.platform.sync.context import SyncContext
from airweave.platform.sync.entity_processor import EntityProcessor
from airweave.platform.sync.stream import AsyncSourceStream
from airweave.platform.sync.worker_pool import AsyncWorkerPool
from airweave.platform.utils.error_utils import get_error_message


class SyncOrchestrator:
    """Orchestrates data synchronization from sources to destinations.

    Pull-based approach: entities are pulled from the stream only when a worker
    is available to process them immediately.

    Behavior is controlled by SyncContext.should_batch:
      - True  -> micro-batched dual-layer pipeline (batches across parents + inner concurrency)
      - False -> legacy per-entity pipeline (one task per parent)
    """

    def __init__(
        self,
        entity_processor: EntityProcessor,
        worker_pool: AsyncWorkerPool,
        stream: AsyncSourceStream,
        sync_context: SyncContext,
    ):
        """Initialize the sync orchestrator with ALL required components."""
        self.entity_processor = entity_processor
        self.worker_pool = worker_pool
        self.stream = stream  # Stream is now passed in, not created here!
        self.sync_context = sync_context

        # Knobs read from context - use explicit defaults instead of getattr
        self.should_batch: bool = (
            sync_context.should_batch if hasattr(sync_context, "should_batch") else True
        )
        self.batch_size: int = (
            sync_context.batch_size if hasattr(sync_context, "batch_size") else 64
        )
        self.max_batch_latency_ms: int = (
            sync_context.max_batch_latency_ms
            if hasattr(sync_context, "max_batch_latency_ms")
            else 200
        )

    async def run(self) -> schemas.Sync:
        """Execute the synchronization process."""
        final_status = SyncJobStatus.FAILED  # Default to failed, will be updated based on outcome
        error_message: Optional[str] = None  # Track error message for finalization
        try:
            await self._start_sync()
            await self._process_entities()
            await self._cleanup_orphaned_entities_if_needed()
            await self._complete_sync()
            final_status = SyncJobStatus.COMPLETED
            return self.sync_context.sync
        except asyncio.CancelledError:
            # Cooperative cancellation: ensure producer and ALL pending tasks are stopped
            self.sync_context.logger.info("Cancellation requested, handling gracefully...")
            await self._handle_cancellation()
            final_status = SyncJobStatus.CANCELLED
            raise
        except Exception as e:
            error_message = get_error_message(e)
            await self._handle_sync_failure(e)
            final_status = SyncJobStatus.FAILED
            raise
        finally:
            # Always finalize progress and trackers with error message if available
            await self._finalize_progress_and_trackers(final_status, error_message)

            # Always flush guard rail usage to prevent data loss
            try:
                self.sync_context.logger.info("Flushing guard rail usage data...")
                await self.sync_context.guard_rail.flush_all()
            except Exception as flush_error:
                self.sync_context.logger.error(
                    f"Failed to flush guard rail usage: {flush_error}", exc_info=True
                )

    async def _start_sync(self) -> None:
        """Initialize sync job and start all components."""
        self.sync_context.logger.info("Starting sync job")

        # Start the stream (worker pool doesn't need starting)
        await self.stream.start()

        started_at = utc_now_naive()
        await sync_job_service.update_status(
            sync_job_id=self.sync_context.sync_job.id,
            status=SyncJobStatus.RUNNING,
            ctx=self.sync_context.ctx,
            started_at=started_at,
        )

        self.sync_context.sync_job.started_at = started_at

        business_events.track_sync_started(
            ctx=self.sync_context.ctx,
            sync_id=self.sync_context.sync.id,
            source_type=self.sync_context.connection.short_name,
            collection_id=self.sync_context.collection.id,
        )

    async def _process_entities(self) -> None:
        """Dispatch to batched or unbatched processing depending on the context flag."""
        if self.should_batch:
            await self._process_entities_batched()
        else:
            await self._process_entities_unbatched()

    # ------------------------------ Batched path ------------------------------
    async def _process_entities_batched(self) -> None:  # noqa: C901
        """Process entities using micro-batching with bounded inner concurrency."""
        source_node = self.sync_context.dag.get_source_node()

        self.entity_processor.initialize_tracking(self.sync_context)

        self.sync_context.logger.info(
            f"Starting pull-based processing from source {self.sync_context.source._name} "
            f"(max workers: {self.worker_pool.max_workers}, "
            f"batch_size: {self.batch_size}, max_batch_latency_ms: {self.max_batch_latency_ms})"
        )

        stream_error: Optional[Exception] = None
        pending_tasks: set[asyncio.Task] = set()

        # Micro-batch aggregation state
        batch_buffer: list = []
        flush_deadline: Optional[float] = None  # event-loop time when we must flush

        try:
            # Use the pre-created stream (already started in _start_sync)
            async for entity in self.stream.get_entities():
                try:
                    await self.sync_context.guard_rail.is_allowed(ActionType.ENTITIES)
                except (UsageLimitExceededException, PaymentRequiredException) as guard_error:
                    self.sync_context.logger.error(
                        f"Guard rail check failed: {type(guard_error).__name__}: {str(guard_error)}"
                    )
                    stream_error = guard_error
                    # Flush any buffered work so we don't drop it
                    if batch_buffer:
                        pending_tasks = await self._submit_batch_and_trim(
                            batch_buffer, pending_tasks, source_node
                        )
                        batch_buffer = []
                        flush_deadline = None
                    break

                # Handle skipped entities without using a worker
                if entity.airweave_system_metadata.should_skip:
                    self.sync_context.logger.debug(f"Skipping entity: {entity.entity_id}")
                    await self.sync_context.progress.increment("skipped", 1)
                    continue

                # Accumulate into batch
                batch_buffer.append(entity)

                # Set a latency-based flush deadline on first element
                if flush_deadline is None and self.max_batch_latency_ms > 0:
                    flush_deadline = (
                        asyncio.get_running_loop().time() + self.max_batch_latency_ms / 1000.0
                    )

                # Size-based flush
                if len(batch_buffer) >= self.batch_size:
                    pending_tasks = await self._submit_batch_and_trim(
                        batch_buffer, pending_tasks, source_node
                    )
                    batch_buffer = []
                    flush_deadline = None
                    continue

                # Time-based flush (checked when new items arrive)
                if (
                    flush_deadline is not None
                    and asyncio.get_running_loop().time() >= flush_deadline
                ):
                    pending_tasks = await self._submit_batch_and_trim(
                        batch_buffer, pending_tasks, source_node
                    )
                    batch_buffer = []
                    flush_deadline = None

            # End-of-stream: flush any remaining buffered entities
            if batch_buffer:
                pending_tasks = await self._submit_batch_and_trim(
                    batch_buffer, pending_tasks, source_node
                )
                batch_buffer = []
                flush_deadline = None

        except asyncio.CancelledError as e:
            # Propagate cancellation: set stream_error so finalize cancels tasks and stop stream
            stream_error = e
            self.sync_context.logger.info("Cancelled during batched processing; finalizing...")
        except Exception as e:
            stream_error = e
            self.sync_context.logger.error(f"Error during entity streaming: {get_error_message(e)}")
        finally:
            # Clean up stream and tasks
            await self._finalize_stream_and_tasks(self.stream, stream_error, pending_tasks)

            # Re-raise error if there was one
            if stream_error:
                raise stream_error

    async def _submit_batch_and_trim(
        self,
        batch: list,
        pending_tasks: set[asyncio.Task],
        source_node: schemas.DagNode,
    ) -> set[asyncio.Task]:
        """Submit a micro-batch to the worker pool and trim to max parallelism if needed."""
        if not batch:
            return pending_tasks

        task = await self.worker_pool.submit(
            self.entity_processor.process_batch,
            entities=list(batch),
            source_node=source_node,
            sync_context=self.sync_context,
        )
        pending_tasks.add(task)

        if len(pending_tasks) >= self.worker_pool.max_workers:
            pending_tasks = await self._handle_completed_tasks(pending_tasks)

        return pending_tasks

    # ----------------------------- Unbatched path -----------------------------
    async def _process_entities_unbatched(self) -> None:  # noqa: C901
        """Process entities one-at-a-time (legacy path)."""
        source_node = self.sync_context.dag.get_source_node()

        self.entity_processor.initialize_tracking(self.sync_context)

        self.sync_context.logger.info(
            f"Starting pull-based processing from source {self.sync_context.source._name} "
            f"(max workers: {self.worker_pool.max_workers})"
        )

        stream_error: Optional[Exception] = None
        pending_tasks: set[asyncio.Task] = set()

        try:
            # Use the pre-created stream (already started in _start_sync)
            async for entity in self.stream.get_entities():
                try:
                    await self.sync_context.guard_rail.is_allowed(ActionType.ENTITIES)
                except (UsageLimitExceededException, PaymentRequiredException) as guard_error:
                    self.sync_context.logger.error(
                        f"Guard rail check failed: {type(guard_error).__name__}: {str(guard_error)}"
                    )
                    stream_error = guard_error
                    break

                # Handle skipped entities safely
                # Entities always have airweave_system_metadata with should_skip defaulting to False
                if entity.airweave_system_metadata.should_skip:
                    self.sync_context.logger.debug(f"Skipping entity: {entity.entity_id}")
                    await self.sync_context.progress.increment("skipped", 1)
                    continue

                # Submit per-entity processing
                task = await self.worker_pool.submit(
                    self.entity_processor.process,
                    entity=entity,
                    source_node=source_node,
                    sync_context=self.sync_context,
                )
                pending_tasks.add(task)

                # Trim when we reach parallelism cap
                if len(pending_tasks) >= self.worker_pool.max_workers:
                    pending_tasks = await self._handle_completed_tasks(pending_tasks)

        except asyncio.CancelledError as e:
            stream_error = e
            self.sync_context.logger.info("Cancelled during unbatched processing; finalizing...")
        except Exception as e:
            stream_error = e
            self.sync_context.logger.error(f"Error during entity streaming: {get_error_message(e)}")
        finally:
            # Clean up stream and tasks
            await self._finalize_stream_and_tasks(self.stream, stream_error, pending_tasks)

            # Re-raise error if there was one
            if stream_error:
                raise stream_error

    # ----------------------------- Shared helpers -----------------------------
    async def _handle_completed_tasks(self, pending_tasks: set[asyncio.Task]) -> set[asyncio.Task]:
        """Handle completed tasks and check for exceptions."""
        completed, pending_tasks = await asyncio.wait(
            pending_tasks, return_when=asyncio.FIRST_COMPLETED
        )
        for task in completed:
            if task.exception():
                raise task.exception()
        return pending_tasks

    async def _wait_for_remaining_tasks(self, pending_tasks: set[asyncio.Task]) -> None:
        """Wait for all remaining tasks to complete and handle exceptions."""
        if pending_tasks:
            self.sync_context.logger.debug(
                f"Waiting for {len(pending_tasks)} remaining tasks to complete"
            )
            done, _ = await asyncio.wait(pending_tasks)
            for task in done:
                if not task.cancelled() and task.exception():
                    self.sync_context.logger.warning(
                        f"Task failed with exception: {task.exception()}"
                    )

    async def _finalize_stream_and_tasks(
        self,
        stream: AsyncSourceStream,
        stream_error: Optional[Exception],
        pending_tasks: set[asyncio.Task],
    ) -> None:
        """Finalize ONLY the stream and pending tasks."""
        # 1. Stop or cancel the stream based on error type
        if isinstance(stream_error, asyncio.CancelledError):
            await stream.cancel()
        else:
            await stream.stop()

        # 2. Cancel pending tasks if there was an error
        if stream_error:
            self.sync_context.logger.info(
                f"Cancelling {len(pending_tasks)} pending tasks due to error..."
            )
            for task in pending_tasks:
                task.cancel()

        # 3. Wait for all tasks to complete
        await self._wait_for_remaining_tasks(pending_tasks)

    async def _cleanup_orphaned_entities_if_needed(self) -> None:
        """Cleanup orphaned entities based on sync type."""
        has_cursor_data = bool(
            hasattr(self.sync_context, "cursor")
            and self.sync_context.cursor
            and self.sync_context.cursor.cursor_data
        )
        should_cleanup = self.sync_context.force_full_sync or not has_cursor_data

        if should_cleanup:
            if self.sync_context.force_full_sync:
                self.sync_context.logger.info(
                    "🧹 Starting orphaned entity cleanup phase (FORCED FULL SYNC - "
                    "daily cleanup schedule)."
                )
            else:
                self.sync_context.logger.info(
                    "🧹 Starting orphaned entity cleanup phase (first sync - no cursor data)"
                )
            await self.entity_processor.cleanup_orphaned_entities(self.sync_context)
        elif has_cursor_data and not self.sync_context.force_full_sync:
            self.sync_context.logger.info(
                "⏩ Skipping orphaned entity cleanup for INCREMENTAL sync "
                "(cursor data exists, only changed entities are processed)"
            )

    async def _finalize_progress_and_trackers(
        self, status: SyncJobStatus, error: Optional[str] = None
    ) -> None:
        """Finalize progress tracking and entity state tracker.

        Args:
            status: The final status of the sync job
            error: Optional error message if the sync failed
        """
        # Publish progress finalization
        await self.sync_context.progress.finalize(status)

        # Publish entity state tracker finalization with error message if available
        if getattr(self.sync_context, "entity_state_tracker", None):
            await self.sync_context.entity_state_tracker.finalize(status, error)

    async def _complete_sync(self) -> None:
        """Mark sync job as completed with final statistics."""
        stats = getattr(self.sync_context.progress, "stats", None)

        # Save cursor data if it exists (for incremental syncs)
        await self._save_cursor_data()

        await sync_job_service.update_status(
            sync_job_id=self.sync_context.sync_job.id,
            status=SyncJobStatus.COMPLETED,
            ctx=self.sync_context.ctx,
            completed_at=utc_now_naive(),
            stats=stats,
        )

        # Track sync completed
        from airweave.analytics import business_events

        entities_processed = 0
        entities_synced = 0  # NEW: actual work done (for billing)
        duration_ms = 0

        if stats:
            # Total operations (for operational metrics)
            entities_processed = (
                stats.inserted + stats.updated + stats.deleted + stats.kept + stats.skipped
            )
            # Actual entities synced (for billing/usage tracking)
            entities_synced = stats.inserted + stats.updated

        # Calculate duration from sync job start to completion
        if (
            self.sync_context.sync_job
            and hasattr(self.sync_context.sync_job, "started_at")
            and self.sync_context.sync_job.started_at is not None
        ):
            duration_ms = int(
                (utc_now_naive() - self.sync_context.sync_job.started_at).total_seconds() * 1000
            )

        business_events.track_sync_completed(
            ctx=self.sync_context.ctx,
            sync_id=self.sync_context.sync.id,
            entities_processed=entities_processed,
            entities_synced=entities_synced,  # NEW parameter
            stats=stats,  # NEW: pass full stats for breakdown
            duration_ms=duration_ms,
        )

        self.sync_context.logger.info(
            f"Completed sync job {self.sync_context.sync_job.id} successfully. Stats: {stats}"
        )

    async def _save_cursor_data(self) -> None:
        """Save cursor data to database if it exists."""
        if not hasattr(self.sync_context, "cursor") or not self.sync_context.cursor.cursor_data:
            if self.sync_context.force_full_sync:
                self.sync_context.logger.info(
                    "📝 No cursor data to save from forced "
                    "full sync (source may not support cursor tracking)"
                )
            return

        try:
            async with get_db_context() as db:
                await sync_cursor_service.create_or_update_cursor(
                    db=db,
                    sync_id=self.sync_context.sync.id,
                    cursor_data=self.sync_context.cursor.cursor_data,
                    ctx=self.sync_context.ctx,
                    cursor_field=self.sync_context.cursor.cursor_field,
                )
                if self.sync_context.force_full_sync:
                    self.sync_context.logger.info(
                        f"💾 Saved cursor data from"
                        f"forced full sync for sync {self.sync_context.sync.id}"
                    )
                else:
                    self.sync_context.logger.info(
                        f"💾 Saved cursor data for sync {self.sync_context.sync.id}"
                    )
        except Exception as e:
            self.sync_context.logger.error(
                f"Failed to save cursor data for sync {self.sync_context.sync.id}: {e}",
                exc_info=True,
            )

    async def _handle_sync_failure(self, error: Exception) -> None:
        """Handle sync failure by updating job status with error details."""
        error_message = get_error_message(error)
        self.sync_context.logger.error(
            f"Sync job {self.sync_context.sync_job.id} failed: {error_message}", exc_info=True
        )

        stats = getattr(self.sync_context.progress, "stats", None)

        await sync_job_service.update_status(
            sync_job_id=self.sync_context.sync_job.id,
            status=SyncJobStatus.FAILED,
            ctx=self.sync_context.ctx,
            error=error_message,
            failed_at=utc_now_naive(),
            stats=stats,
        )

        # Calculate duration from start to failure
        if not self.sync_context.sync_job.started_at:
            # This can happen if failure occurs during _start_sync before
            # the job status is updated with started_at
            self.sync_context.logger.warning(
                "sync_job.started_at is None - failure occurred very early"
            )
            duration_ms = 0
        else:
            duration_ms = int(
                (utc_now_naive() - self.sync_context.sync_job.started_at).total_seconds() * 1000
            )

        business_events.track_sync_failed(
            ctx=self.sync_context.ctx,
            sync_id=self.sync_context.sync.id,
            error=error_message,
            duration_ms=duration_ms,
        )

    async def _handle_cancellation(self) -> None:
        """Centralized cancellation handler - explicit and immediate."""
        self.sync_context.logger.info("Handling cancellation...")

        # 1. Cancel all pending tasks IMMEDIATELY
        if self.worker_pool:
            await self.worker_pool.cancel_all()

        # 2. Cancel stream to stop producer
        await self.stream.cancel()

        # 3. Update job status to final CANCELLED state
        await sync_job_service.update_status(
            sync_job_id=self.sync_context.sync_job.id,
            status=SyncJobStatus.CANCELLED,
            ctx=self.sync_context.ctx,
            completed_at=utc_now_naive(),
        )

        # 4. Track sync cancelled
        if not self.sync_context.sync_job.started_at:
            # This can happen if cancellation occurs during _start_sync before
            # the job status is updated with started_at
            self.sync_context.logger.warning(
                "sync_job.started_at is None - cancellation occurred very early"
            )
            duration_ms = 0
        else:
            duration_ms = int(
                (utc_now_naive() - self.sync_context.sync_job.started_at).total_seconds() * 1000
            )

        business_events.track_sync_cancelled(
            ctx=self.sync_context.ctx,
            source_short_name=self.sync_context.connection.short_name,
            source_connection_id=self.sync_context.connection.id,
            duration_ms=duration_ms,
        )
