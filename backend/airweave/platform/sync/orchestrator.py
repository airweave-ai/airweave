"""Module for data synchronization with TRUE batching + toggleable batching."""

import asyncio
import time
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
from airweave.platform.sync.entity_pipeline import EntityPipeline
from airweave.platform.sync.exceptions import EntityProcessingError, SyncFailureError
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
        entity_pipeline: EntityPipeline,
        worker_pool: AsyncWorkerPool,
        stream: AsyncSourceStream,
        sync_context: SyncContext,
    ):
        """Initialize the sync orchestrator with ALL required components."""
        self.entity_pipeline = entity_pipeline
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
        """Execute the synchronization process with adjacent access control pipeline."""
        final_status = SyncJobStatus.FAILED  # Default to failed, updated on outcome
        error_message: Optional[str] = None  # Track error message for finalization
        try:
            # Phase 1: Start sync
            phase_start = time.time()
            self.sync_context.logger.info("🚀 PHASE 1: Starting sync initialization...")
            await self._start_sync()
            self.sync_context.logger.info(f"✅ PHASE 1 complete ({time.time() - phase_start:.2f}s)")

            # Phase 2: Process entities
            phase_start = time.time()
            self.sync_context.logger.info("🚀 PHASE 2: Processing entities from source...")
            await self._process_entities()
            await self._process_access_control_memberships()
            self.sync_context.logger.info(f"✅ PHASE 2 complete ({time.time() - phase_start:.2f}s)")

            # Phase 3: Cleanup orphaned entities
            phase_start = time.time()
            self.sync_context.logger.info("🚀 PHASE 3: Cleaning up orphaned entities...")
            await self._cleanup_orphaned_entities_if_needed()
            self.sync_context.logger.info(f"✅ PHASE 3 complete ({time.time() - phase_start:.2f}s)")

            # Phase 4: Complete sync
            phase_start = time.time()
            self.sync_context.logger.info("🚀 PHASE 4: Finalizing sync...")

            # Phase 5: Complete sync
            phase_start = time.time()
            self.sync_context.logger.info("🚀 PHASE 5: Completing sync...")
            await self._complete_sync()
            self.sync_context.logger.info(f"✅ PHASE 5 complete ({time.time() - phase_start:.2f}s)")

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

            # Always cleanup temp files to prevent pod eviction
            # Note: This runs in finally block, so it executes even if sync failed
            # We don't raise cleanup errors to avoid masking the original sync error
            try:
                self.sync_context.logger.info("Running final temp file cleanup...")
                await self.entity_pipeline.cleanup_temp_files(self.sync_context)
            except Exception as cleanup_error:
                # Never raise from cleanup - we want the original sync error to propagate
                # If sync succeeded but cleanup failed, that's logged but not re-raised
                self.sync_context.logger.error(
                    f"Temp file cleanup failed (non-fatal in finally block): {cleanup_error}",
                    exc_info=True,
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

    async def _process_entities(self) -> None:  # noqa: C901
        """Process entities using micro-batching with bounded inner concurrency."""
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
                            batch_buffer, pending_tasks
                        )
                        batch_buffer = []
                        flush_deadline = None
                    break

                # Accumulate into batch
                batch_buffer.append(entity)

                # Set a latency-based flush deadline on first element
                if flush_deadline is None and self.max_batch_latency_ms > 0:
                    flush_deadline = (
                        asyncio.get_running_loop().time() + self.max_batch_latency_ms / 1000.0
                    )

                # Size-based flush
                if len(batch_buffer) >= self.batch_size:
                    pending_tasks = await self._submit_batch_and_trim(batch_buffer, pending_tasks)
                    batch_buffer = []
                    flush_deadline = None
                    continue

                # Time-based flush (checked when new items arrive)
                if (
                    flush_deadline is not None
                    and asyncio.get_running_loop().time() >= flush_deadline
                ):
                    pending_tasks = await self._submit_batch_and_trim(batch_buffer, pending_tasks)
                    batch_buffer = []
                    flush_deadline = None

            # End-of-stream: flush any remaining buffered entities
            if batch_buffer:
                pending_tasks = await self._submit_batch_and_trim(batch_buffer, pending_tasks)
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
    ) -> set[asyncio.Task]:
        """Submit a micro-batch to the worker pool and trim to max parallelism if needed."""
        if not batch:
            return pending_tasks

        task = await self.worker_pool.submit(
            self.entity_pipeline.process,
            entities=list(batch),
            sync_context=self.sync_context,
        )
        pending_tasks.add(task)

        # Check for completed tasks and fail fast on sync errors
        pending_tasks = await self._check_completed_tasks_fail_fast(pending_tasks)

        # Trim if we've hit max parallelism
        if len(pending_tasks) >= self.worker_pool.max_workers:
            pending_tasks = await self._handle_completed_tasks(pending_tasks)

        return pending_tasks

    async def _check_completed_tasks_fail_fast(
        self, pending_tasks: set[asyncio.Task]
    ) -> set[asyncio.Task]:
        """Check any completed tasks and fail immediately on sync errors.

        This provides fail-fast behavior - we don't wait for all tasks to finish
        before detecting critical errors.
        """
        completed = {t for t in pending_tasks if t.done()}
        if not completed:
            return pending_tasks

        # Check errors using shared logic
        entity_failures = self._check_task_errors(completed)

        # Remove completed tasks from pending set
        pending_tasks -= completed

        # Track entity failures
        if entity_failures:
            await self.sync_context.progress.increment("skipped", len(entity_failures))

        return pending_tasks

    # ----------------------------- Shared helpers -----------------------------
    def _check_task_errors(self, tasks: set[asyncio.Task]) -> list[EntityProcessingError]:
        """Check tasks for errors and handle based on error type.

        Args:
            tasks: Set of tasks to check for errors

        Returns:
            List of EntityProcessingError instances (recoverable errors)

        Raises:
            SyncFailureError: On explicit sync failure
            Exception: On unexpected errors
        """
        entity_failures = []

        for task in tasks:
            if not task.cancelled() and task.exception():
                exc = task.exception()

                if isinstance(exc, EntityProcessingError):
                    # Entity-level error - track for skipping
                    entity_failures.append(exc)
                    self.sync_context.logger.warning(f"Entity processing error: {exc}")
                elif isinstance(exc, SyncFailureError):
                    # Explicit sync failure - fail immediately
                    self.sync_context.logger.error(f"Sync failure detected: {exc}")
                    raise exc
                else:
                    # Unexpected error - also fail sync
                    self.sync_context.logger.error(
                        f"Unexpected error in task: {exc}", exc_info=True
                    )
                    raise exc

        return entity_failures

    async def _handle_completed_tasks(self, pending_tasks: set[asyncio.Task]) -> set[asyncio.Task]:
        """Handle completed tasks and check for exceptions.

        Waits for at least one task to complete when we hit max parallelism.
        """
        completed, pending_tasks = await asyncio.wait(
            pending_tasks, return_when=asyncio.FIRST_COMPLETED
        )

        # Check errors using shared logic
        entity_failures = self._check_task_errors(completed)

        # Increment skipped count for entity failures
        if entity_failures:
            await self.sync_context.progress.increment("skipped", len(entity_failures))
            self.sync_context.logger.info(
                f"Skipped {len(entity_failures)} entities due to processing errors"
            )

        return pending_tasks

    async def _wait_for_remaining_tasks(self, pending_tasks: set[asyncio.Task]) -> None:
        """Wait for all remaining tasks to complete and handle exceptions."""
        if pending_tasks:
            self.sync_context.logger.debug(
                f"Waiting for {len(pending_tasks)} remaining tasks to complete"
            )
            done, _ = await asyncio.wait(pending_tasks)

            # Check errors using shared logic
            entity_failures = self._check_task_errors(done)

            # Increment skipped count for entity failures
            if entity_failures:
                await self.sync_context.progress.increment("skipped", len(entity_failures))
                self.sync_context.logger.info(
                    f"Skipped {len(entity_failures)} entities due to processing errors"
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

    async def _process_access_control_memberships(self) -> None:
        """Process access control memberships using adjacent pipeline.

        This runs AFTER entity sync, reusing same patterns:
        - AsyncSourceStream for streaming
        - AsyncWorkerPool for concurrency
        - Same batching logic
        - Separate progress tracking
        """
        # Check if source supports membership extraction
        if not hasattr(self.sync_context.source, "generate_access_control_memberships"):
            self.sync_context.logger.info(
                "⏩ Skipping access control sync - source doesn't implement it"
            )
            return

        self.sync_context.logger.info("🔐 Starting access control membership sync phase...")

        # Create access control pipeline (simplified vs entity pipeline)
        from airweave.platform.sync.access_control_pipeline import AccessControlPipeline

        access_control_pipeline = AccessControlPipeline()

        # Create separate stream for memberships (reuse AsyncSourceStream pattern)
        membership_stream = AsyncSourceStream(
            source_generator=self.sync_context.source.generate_access_control_memberships(),
            queue_size=1000,  # Smaller queue - typically fewer memberships than entities
            logger=self.sync_context.logger.with_context(component="access_control_stream"),
        )

        # Start stream
        await membership_stream.start()

        # Reuse same worker pool and batching pattern
        stream_error: Optional[Exception] = None
        pending_tasks: set[asyncio.Task] = set()
        batch_buffer = []
        flush_deadline = None

        try:
            async for membership in membership_stream.get_entities():
                # Accumulate into batch
                batch_buffer.append(membership)

                # Set flush deadline
                if flush_deadline is None and self.max_batch_latency_ms > 0:
                    flush_deadline = (
                        asyncio.get_running_loop().time() + self.max_batch_latency_ms / 1000.0
                    )

                # Size-based flush
                if len(batch_buffer) >= self.batch_size:
                    pending_tasks = await self._submit_membership_batch(
                        batch_buffer, pending_tasks, access_control_pipeline
                    )
                    batch_buffer = []
                    flush_deadline = None
                    continue

                # Time-based flush
                if (
                    flush_deadline is not None
                    and asyncio.get_running_loop().time() >= flush_deadline
                ):
                    pending_tasks = await self._submit_membership_batch(
                        batch_buffer, pending_tasks, access_control_pipeline
                    )
                    batch_buffer = []
                    flush_deadline = None

            # Flush remaining
            if batch_buffer:
                pending_tasks = await self._submit_membership_batch(
                    batch_buffer, pending_tasks, access_control_pipeline
                )

        except Exception as e:
            stream_error = e
            self.sync_context.logger.error(
                f"Error during membership streaming: {get_error_message(e)}"
            )

        finally:
            # Cleanup stream and tasks (reuse existing pattern)
            await self._finalize_stream_and_tasks(membership_stream, stream_error, pending_tasks)

            if stream_error:
                raise stream_error

        self.sync_context.logger.info("✅ Access control membership sync complete")

    async def _submit_membership_batch(
        self, batch: list, pending_tasks: set[asyncio.Task], pipeline
    ) -> set[asyncio.Task]:
        """Submit membership batch to worker pool (reuses entity pattern).

        Args:
            batch: List of membership objects
            pending_tasks: Set of currently pending tasks
            pipeline: AccessControlPipeline instance

        Returns:
            Updated set of pending tasks
        """
        if not batch:
            return pending_tasks

        task = await self.worker_pool.submit(
            pipeline.process, memberships=list(batch), sync_context=self.sync_context
        )
        pending_tasks.add(task)

        # Trim if at max parallelism
        if len(pending_tasks) >= self.worker_pool.max_workers:
            completed, pending_tasks = await asyncio.wait(
                pending_tasks, return_when=asyncio.FIRST_COMPLETED
            )

        return pending_tasks

    async def _cleanup_orphaned_entities_if_needed(self) -> None:
        """Cleanup orphaned entities based on sync type."""
        has_cursor_data = bool(
            hasattr(self.sync_context, "cursor")
            and self.sync_context.cursor
            and self.sync_context.cursor.cursor_data
        )

        # Check if source supports continuous/incremental sync
        source_supports_continuous = getattr(
            self.sync_context.source, "_supports_continuous", False
        )

        # Cleanup should run if:
        # 1. Forced full sync (daily cleanup schedule), OR
        # 2. First sync (no cursor data), OR
        # 3. Source doesn't support incremental sync (every sync is a full sync)
        should_cleanup = (
            self.sync_context.force_full_sync
            or not has_cursor_data
            or not source_supports_continuous
        )

        if should_cleanup:
            if self.sync_context.force_full_sync:
                self.sync_context.logger.info(
                    "🧹 Starting orphaned entity cleanup phase (FORCED FULL SYNC - "
                    "daily cleanup schedule)."
                )
            elif not source_supports_continuous:
                self.sync_context.logger.info(
                    "🧹 Starting orphaned entity cleanup phase (full sync - "
                    "source doesn't support incremental sync)"
                )
            else:
                self.sync_context.logger.info(
                    "🧹 Starting orphaned entity cleanup phase (first sync - no cursor data)"
                )
            await self.entity_pipeline.cleanup_orphaned_entities(self.sync_context)
        elif (
            has_cursor_data and not self.sync_context.force_full_sync and source_supports_continuous
        ):
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
