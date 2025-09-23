"""Module for data synchronization with improved architecture + toggleable batching."""

import asyncio
from typing import Optional

from airweave import schemas
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

    Uses a pull-based approach where entities are only pulled from the
    stream when a worker is available to process them immediately.

    Behavior is controlled by SyncContext.should_batch:
      - True  -> micro-batched pipeline (batches entities together for better performance)
      - False -> legacy per-entity pipeline (exact same as original, one task per entity)
    """

    def __init__(
        self,
        entity_processor: EntityProcessor,
        worker_pool: AsyncWorkerPool,
        sync_context: SyncContext,
    ):
        """Initialize the sync orchestrator.

        Args:
            entity_processor: Processes entities through transformation pipeline
            worker_pool: Manages concurrent task execution with semaphore control
            sync_context: Contains all resources needed for synchronization
        """
        self.entity_processor = entity_processor
        self.worker_pool = worker_pool
        self.sync_context = sync_context

        # Queue size provides buffering for bursty sources
        # Workers pull from this queue when ready
        self.stream_buffer_size = 10000

        # Batching configuration (read from context, with defaults)
        self.should_batch = sync_context.should_batch
        self.batch_size = sync_context.batch_size
        self.max_batch_latency_ms = sync_context.max_batch_latency_ms

    async def run(self) -> schemas.Sync:
        """Execute the synchronization process.

        Returns:
            The sync object after completion

        Raises:
            Exception: If sync fails, after updating job status
        """
        try:
            await self._start_sync()
            await self._process_entities()
            await self._complete_sync()

            return self.sync_context.sync

        except Exception as e:
            await self._handle_sync_failure(e)
            raise
        finally:
            # Always flush guard rail usage to prevent data loss
            try:
                self.sync_context.logger.info("Flushing guard rail usage data...")
                await self.sync_context.guard_rail.flush_all()
            except Exception as flush_error:
                self.sync_context.logger.error(
                    f"Failed to flush guard rail usage: {flush_error}", exc_info=True
                )

    async def _start_sync(self) -> None:
        """Initialize sync job and update status to in-progress."""
        self.sync_context.logger.info("Starting sync job")

        await sync_job_service.update_status(
            sync_job_id=self.sync_context.sync_job.id,
            status=SyncJobStatus.RUNNING,
            ctx=self.sync_context.ctx,
            started_at=utc_now_naive(),
        )

        # Track sync started
        from airweave.analytics import business_events

        business_events.track_sync_started(
            ctx=self.sync_context.ctx,
            sync_id=self.sync_context.sync.id,
            source_type=self.sync_context.source_connection.short_name,
            collection_id=self.sync_context.collection.id,
        )

    async def _process_entities(self) -> None:
        """Dispatch to batched or unbatched processing depending on context configuration."""
        if self.should_batch:
            await self._process_entities_batched()
        else:
            await self._process_entities_unbatched()

    # ------------------------------ Original unbatched path (EXACT copy) ----------------------
    async def _process_entities_unbatched(self) -> None:  # noqa: C901
        """Process entities with explicit stream lifecycle management (ORIGINAL LOGIC)."""
        source_node = self.sync_context.dag.get_source_node()

        self.sync_context.logger.info(
            f"Starting pull-based processing from source {self.sync_context.source._name} "
            f"(buffer: {self.stream_buffer_size}, max workers: {self.worker_pool.max_workers})"
        )

        stream = None
        stream_error: Optional[Exception] = None
        pending_tasks: set[asyncio.Task] = set()

        try:
            # Create stream outside the async with to have explicit control
            stream = AsyncSourceStream(
                self.sync_context.source.generate_entities(),
                queue_size=self.stream_buffer_size,
                logger=self.sync_context.logger,
            )
            await stream.start()

            async for entity in stream.get_entities():
                try:
                    # Check guard rail
                    await self.sync_context.guard_rail.is_allowed(ActionType.ENTITIES)
                except (UsageLimitExceededException, PaymentRequiredException) as guard_error:
                    self.sync_context.logger.error(
                        f"Guard rail check failed: {type(guard_error).__name__}: {str(guard_error)}"
                    )
                    stream_error = guard_error
                    break  # Exit the loop cleanly instead of raising

                # Handle skipped entities without using a worker
                if entity.airweave_system_metadata.should_skip:
                    self.sync_context.logger.debug(f"Skipping entity: {entity.entity_id}")
                    await self.sync_context.progress.increment("skipped")
                    continue

                # Submit entity processing to worker pool
                task = await self.worker_pool.submit(
                    self.entity_processor.process,
                    entity=entity,
                    source_node=source_node,
                    sync_context=self.sync_context,
                )
                pending_tasks.add(task)

                # Clean up completed tasks periodically
                if len(pending_tasks) >= self.worker_pool.max_workers:
                    pending_tasks = await self._handle_completed_tasks(pending_tasks)

        except Exception as e:
            stream_error = e
            self.sync_context.logger.error(f"Error during entity streaming: {get_error_message(e)}")

        finally:
            await self._finalize_stream_and_cleanup(stream, stream_error, pending_tasks)

    # ------------------------------ NEW batched path ------------------------------
    async def _process_entities_batched(self) -> None:  # noqa: C901
        """Process entities using micro-batching with controlled concurrency."""
        source_node = self.sync_context.dag.get_source_node()

        self.sync_context.logger.info(
            f"Starting batched pull-based processing from source {self.sync_context.source._name} "
            f"(buffer: {self.stream_buffer_size}, max workers: {self.worker_pool.max_workers}, "
            f"batch_size: {self.batch_size}, max_batch_latency_ms: {self.max_batch_latency_ms})"
        )

        stream = None
        stream_error: Optional[Exception] = None
        pending_tasks: set[asyncio.Task] = set()

        # Micro-batch aggregation state
        batch_buffer: list = []
        flush_deadline: Optional[float] = None  # event-loop time when we must flush

        try:
            stream = AsyncSourceStream(
                self.sync_context.source.generate_entities(),
                queue_size=self.stream_buffer_size,
                logger=self.sync_context.logger,
            )
            await stream.start()

            async for entity in stream.get_entities():
                try:
                    # Check guard rail
                    await self.sync_context.guard_rail.is_allowed(ActionType.ENTITIES)
                except (UsageLimitExceededException, PaymentRequiredException) as guard_error:
                    self.sync_context.logger.error(
                        f"Guard rail check failed: {type(guard_error).__name__}: {str(guard_error)}"
                    )
                    stream_error = guard_error
                    # Before breaking, flush any buffered work so we don't drop it
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
                    await self.sync_context.progress.increment("skipped")
                    continue

                # Accumulate into batch
                batch_buffer.append(entity)

                # Set a latency-based flush deadline on first element
                if flush_deadline is None and self.max_batch_latency_ms > 0:
                    flush_deadline = (
                        asyncio.get_event_loop().time() + self.max_batch_latency_ms / 1000.0
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
                if flush_deadline is not None and asyncio.get_event_loop().time() >= flush_deadline:
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

        except Exception as e:
            stream_error = e
            self.sync_context.logger.error(f"Error during entity streaming: {get_error_message(e)}")

        finally:
            await self._finalize_stream_and_cleanup(stream, stream_error, pending_tasks)

    async def _submit_batch_and_trim(
        self,
        batch: list,
        pending_tasks: set[asyncio.Task],
        source_node: schemas.DagNode,
    ) -> set[asyncio.Task]:
        """Submit a micro-batch to the worker pool and trim to max parallelism if needed."""
        if not batch:
            return pending_tasks

        # Submit batch to EntityProcessor.process_batch (which internally uses original logic)
        task = await self.worker_pool.submit(
            self.entity_processor.process_batch,
            entities=list(batch),
            source_node=source_node,
            sync_context=self.sync_context,
        )
        pending_tasks.add(task)

        # Clean up completed tasks when we hit the parallelism limit
        if len(pending_tasks) >= self.worker_pool.max_workers:
            pending_tasks = await self._handle_completed_tasks(pending_tasks)

        return pending_tasks

    # ------------------------------ Shared helpers (from original) ------------------------------
    async def _handle_completed_tasks(self, pending_tasks: set[asyncio.Task]) -> set[asyncio.Task]:
        """Handle completed tasks and check for exceptions.

        Args:
            pending_tasks: Set of pending tasks

        Returns:
            Updated set of pending tasks with completed ones removed
        """
        completed, pending_tasks = await asyncio.wait(
            pending_tasks, return_when=asyncio.FIRST_COMPLETED
        )
        # Check for exceptions in completed tasks
        for task in completed:
            if task.exception():
                raise task.exception()
        return pending_tasks

    async def _wait_for_remaining_tasks(self, pending_tasks: set[asyncio.Task]) -> None:
        """Wait for all remaining tasks to complete and handle exceptions.

        Args:
            pending_tasks: Set of pending tasks to wait for
        """
        if pending_tasks:
            self.sync_context.logger.debug(
                f"Waiting for {len(pending_tasks)} remaining tasks to complete"
            )
            done, _ = await asyncio.wait(pending_tasks)
            # Check for exceptions in completed tasks
            for task in done:
                if not task.cancelled() and task.exception():
                    self.sync_context.logger.warning(
                        f"Task failed with exception: {task.exception()}"
                    )

    async def _finalize_stream_and_cleanup(
        self,
        stream: Optional[AsyncSourceStream],
        stream_error: Optional[Exception],
        pending_tasks: set[asyncio.Task],
    ) -> None:
        """Finalize stream and perform cleanup (ORIGINAL LOGIC PRESERVED)."""
        # Always clean up the stream first
        self.sync_context.logger.info("Finalizing stream and cleaning up")
        self.sync_context.logger.info(f"Stream error: {stream_error}")
        if stream:
            await stream.stop()

        # Then handle pending tasks
        if stream_error:
            # Cancel all pending tasks if there was an error
            self.sync_context.logger.info(f"Cancelling {len(pending_tasks)} pending tasks...")
            for task in pending_tasks:
                task.cancel()

        # Wait for all tasks to complete
        await self._wait_for_remaining_tasks(pending_tasks)
        await self.sync_context.progress.finalize(is_complete=(stream_error is None))

        # NEW: Finalize entity state tracker if present
        if self.sync_context.entity_state_tracker:
            error_message = get_error_message(stream_error) if stream_error else None
            await self.sync_context.entity_state_tracker.finalize(
                is_complete=(stream_error is None), error=error_message
            )

        # Clean up orphaned entities after all processing is complete
        #
        # ⚠️ IMPORTANT: ORPHANED ENTITY CLEANUP IS DISABLED FOR INCREMENTAL SYNCS ⚠️
        #
        # The orphaned entity cleanup was designed for full syncs where ALL entities
        # from the source are processed. In incremental syncs, only CHANGED entities
        # are yielded, so unchanged entities would incorrectly appear as "orphaned"
        # and get deleted.
        #
        # For incremental syncs, deletions should only happen through:
        # 1. Explicit deletion entities (e.g., GitHubFileDeletionEntity)
        # 2. NOT through orphaned cleanup
        #
        # TODO: Future improvement could track which entities are expected to be
        # unchanged vs. truly orphaned, allowing cleanup even in incremental syncs.
        #
        # Detection logic:
        # - If cursor data exists, this is an incremental sync (we've synced before)
        # - If no cursor data, this is the first/full sync

        # Check if we should do cleanup
        # Cleanup happens if:
        # 1. force_full_sync is True (daily cleanup run), OR
        # 2. No cursor data exists (first sync or reset)
        has_cursor_data = bool(
            hasattr(self.sync_context, "cursor")
            and self.sync_context.cursor
            and self.sync_context.cursor.cursor_data
        )

        should_cleanup = self.sync_context.force_full_sync or not has_cursor_data

        if not stream_error and should_cleanup:
            try:
                if self.sync_context.force_full_sync:
                    self.sync_context.logger.info(
                        "🧹 Starting orphaned entity cleanup phase (FORCED FULL SYNC - "
                        "daily cleanup schedule). All source entities were fetched to "
                        "accurately identify orphaned entities."
                    )
                else:
                    self.sync_context.logger.info(
                        "🧹 Starting orphaned entity cleanup phase (first sync - no cursor data)"
                    )
                await self.entity_processor.cleanup_orphaned_entities(self.sync_context)
            except Exception as cleanup_error:
                self.sync_context.logger.error(
                    f"💥 Orphaned entity cleanup failed: {get_error_message(cleanup_error)}",
                    exc_info=True,
                )
                raise cleanup_error
        elif has_cursor_data and not self.sync_context.force_full_sync:
            self.sync_context.logger.info(
                "⏩ Skipping orphaned entity cleanup for INCREMENTAL sync "
                "(cursor data exists, only changed entities are processed)"
            )

        # Re-raise the error after cleanup
        if stream_error:
            raise stream_error

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
        duration_ms = 0

        if stats:
            entities_processed = (
                stats.inserted + stats.updated + stats.deleted + stats.kept + stats.skipped
            )

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
            duration_ms=duration_ms,
        )

        self.sync_context.logger.info(
            f"Completed sync job {self.sync_context.sync_job.id} successfully. Stats: {stats}"
        )

    async def _save_cursor_data(self) -> None:
        """Save cursor data to database if it exists.

        Even for forced full syncs, we save the cursor data so the next
        incremental sync knows where to start from.
        """
        if not hasattr(self.sync_context, "cursor") or not self.sync_context.cursor.cursor_data:
            if self.sync_context.force_full_sync:
                self.sync_context.logger.info(
                    "📝 No cursor data to save from forced full sync "
                    "(source may not support cursor tracking)"
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
                        f"💾 Saved cursor data from forced full sync for sync "
                        f"{self.sync_context.sync.id} - next incremental sync will start from here"
                    )
                else:
                    self.sync_context.logger.info(
                        f"💾 Saved cursor data for sync {self.sync_context.sync.id}"
                    )
        except Exception as e:
            # Log at ERROR level since cursor save failures can affect incremental syncs
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

        # Track sync failed
        from airweave.analytics import business_events

        duration_ms = 0

        if (
            self.sync_context.sync_job
            and hasattr(self.sync_context.sync_job, "started_at")
            and self.sync_context.sync_job.started_at is not None
        ):
            # Calculate duration from start to failure
            duration_ms = int(
                (utc_now_naive() - self.sync_context.sync_job.started_at).total_seconds() * 1000
            )

        business_events.track_sync_failed(
            ctx=self.sync_context.ctx,
            sync_id=self.sync_context.sync.id,
            error=error_message,
            duration_ms=duration_ms,
        )
