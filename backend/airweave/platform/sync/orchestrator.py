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
from airweave.platform.contexts import SyncContext
from airweave.platform.contexts.runtime import SyncRuntime
from airweave.platform.sync.access_control_pipeline import AccessControlPipeline
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
        runtime: SyncRuntime,
        access_control_pipeline: AccessControlPipeline,
    ):
        """Initialize the sync orchestrator with ALL required components."""
        self.entity_pipeline = entity_pipeline
        self.worker_pool = worker_pool
        self.stream = stream
        self.sync_context = sync_context
        self.runtime = runtime
        self.access_control_pipeline = access_control_pipeline

        # Batch config from context
        self.should_batch = sync_context.should_batch
        self.batch_size = sync_context.batch_size
        self.max_batch_latency_ms = sync_context.max_batch_latency_ms

    async def run(self) -> schemas.Sync:
        """Execute the synchronization process."""
        final_status = SyncJobStatus.FAILED  # Default to failed, will be updated based on outcome
        error_message: Optional[str] = None  # Track error message for finalization

        # Register worker pool for metrics tracking (using sync_id and sync_job_id)
        # Format: sync_{sync_id}_job_{sync_job_id} for easier parsing in metrics
        pool_id = f"sync_{self.sync_context.sync.id}_job_{self.sync_context.sync_job.id}"
        try:
            from airweave.platform.temporal.worker_metrics import worker_metrics

            worker_metrics.register_worker_pool(pool_id, self.worker_pool)
        except Exception as e:
            self.sync_context.logger.warning(
                f"Failed to register worker pool for metrics: {e}",
                extra={
                    "pool_id": pool_id,
                    "sync_id": str(self.sync_context.sync.id),
                    "sync_job_id": str(self.sync_context.sync_job.id),
                    "error_type": type(e).__name__,
                },
            )

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
            self.sync_context.logger.info(f"✅ PHASE 2 complete ({time.time() - phase_start:.2f}s)")

            # Phase 2.5: Process access control memberships (if source supports it)
            if self._source_supports_access_control():
                phase_start = time.time()
                self.sync_context.logger.info(
                    "🚀 PHASE 2.5: Processing access control memberships..."
                )
                await self._process_access_control_memberships()
                self.sync_context.logger.info(
                    f"✅ PHASE 2.5 complete ({time.time() - phase_start:.2f}s)"
                )

            # Phase 3: Cleanup orphaned entities
            phase_start = time.time()
            self.sync_context.logger.info("🚀 PHASE 3: Cleanup orphaned entities (if needed)...")
            await self._cleanup_orphaned_entities_if_needed()
            self.sync_context.logger.info(f"✅ PHASE 3 complete ({time.time() - phase_start:.2f}s)")

            # Phase 4: Complete sync
            phase_start = time.time()
            self.sync_context.logger.info("🚀 PHASE 4: Finalizing sync...")
            await self._complete_sync()
            self.sync_context.logger.info(f"✅ PHASE 4 complete ({time.time() - phase_start:.2f}s)")

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
            # Note: Removed aggregate metrics recording (histograms/counters)
            # Real-time visibility via Gauge metrics which clear on completion

            # Unregister worker pool from metrics
            try:
                from airweave.platform.temporal.worker_metrics import worker_metrics

                worker_metrics.unregister_worker_pool(pool_id)
            except Exception as e:
                self.sync_context.logger.warning(
                    f"Failed to unregister worker pool from metrics: {e}",
                    extra={
                        "pool_id": pool_id,
                        "sync_id": str(self.sync_context.sync.id),
                        "sync_job_id": str(self.sync_context.sync_job.id),
                        "error_type": type(e).__name__,
                    },
                )

            # Always finalize progress and trackers with error message if available
            await self._finalize_progress_and_trackers(final_status, error_message)

            # Always flush guard rail usage to prevent data loss
            try:
                self.sync_context.logger.info("Flushing guard rail usage data...")
                await self.runtime.guard_rail.flush_all()
            except Exception as flush_error:
                self.sync_context.logger.error(
                    f"Failed to flush guard rail usage: {flush_error}", exc_info=True
                )

            # Always cleanup temp files to prevent pod eviction
            # Note: This runs in finally block, so it executes even if sync failed
            # We don't raise cleanup errors to avoid masking the original sync error
            try:
                self.sync_context.logger.info("Running final temp file cleanup...")
                await self.entity_pipeline.cleanup_temp_files(self.sync_context, self.runtime)
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
            ctx=self.sync_context,
            started_at=started_at,
        )

        self.sync_context.sync_job.started_at = started_at

    async def _process_entities(self) -> None:  # noqa: C901
        """Process entities using micro-batching with bounded inner concurrency."""
        source_name = self.runtime.source.source_name
        self.sync_context.logger.info(
            f"Starting pull-based processing from source {source_name} "
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
                # Check guardrails unless explicitly skipped
                if not self.sync_context.execution_config.behavior.skip_guardrails:
                    try:
                        await self.runtime.guard_rail.is_allowed(ActionType.ENTITIES)
                    except (UsageLimitExceededException, PaymentRequiredException) as guard_error:
                        self.sync_context.logger.error(
                            "Guard rail check failed: {type}: {error}".format(
                                type=type(guard_error).__name__,
                                error=str(guard_error),
                            )
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
            runtime=self.runtime,
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
            await self.runtime.entity_tracker.record_skipped(len(entity_failures))

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
            await self.runtime.entity_tracker.record_skipped(len(entity_failures))
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
                await self.runtime.entity_tracker.record_skipped(len(entity_failures))
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

    async def _cleanup_orphaned_entities_if_needed(self) -> None:
        """Cleanup orphaned entities based on sync type."""
        has_cursor_data = bool(
            hasattr(self.sync_context, "cursor")
            and self.runtime.cursor
            and self.runtime.cursor.cursor_data
        )

        # Check if source supports continuous/incremental sync (class attribute)
        source_class = type(self.runtime.source)
        source_supports_continuous = getattr(source_class, "supports_continuous", False)

        self.sync_context.logger.debug(
            f"Orphan cleanup check: has_cursor_data={has_cursor_data}, "
            f"supports_continuous={source_supports_continuous}, "
            f"force_full_sync={self.sync_context.force_full_sync}"
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
            # Dispatcher handles ALL handlers: Destination, ARF, and Postgres
            await self.entity_pipeline.cleanup_orphaned_entities(self.sync_context, self.runtime)
        elif (
            has_cursor_data and not self.sync_context.force_full_sync and source_supports_continuous
        ):
            self.sync_context.logger.info(
                "⏩ Skipping orphaned entity cleanup for INCREMENTAL sync "
                "(cursor data exists, only changed entities are processed)"
            )

    def _source_supports_access_control(self) -> bool:
        """Check if the source supports access control membership syncing."""
        return getattr(self.runtime.source, "supports_access_control", False)

    async def _process_access_control_memberships(self) -> None:
        """Process access control memberships from the source.

        Delegates all ACL logic to the AccessControlPipeline, which:
        - Decides whether to do incremental or full ACL sync
        - Collects memberships from the source (full) or gets DirSync deltas (incremental)
        - Resolves to actions and dispatches to handlers
        - Handles orphan cleanup (full sync only)
        - Updates the cursor with DirSync cookie

        Publishes progress heartbeats before and after to prevent the
        stuck-job cleanup from cancelling during long-running ACL expansion.
        """
        source = self.runtime.source
        source_name = getattr(source, "_name", "unknown")

        self.sync_context.logger.info(f"Starting access control sync for {source_name}")

        # Publish a progress heartbeat so the stuck-job detector knows we're alive.
        # ACL expansion (especially with 50K+ users) can take a long time without
        # producing entity progress updates, which would otherwise trigger cancellation.
        await self.runtime.state_publisher.publish_progress()

        try:
            await self.access_control_pipeline.process(
                source=source,
                sync_context=self.sync_context,
                runtime=self.runtime,
            )
        except Exception as e:
            self.sync_context.logger.error(
                f"ACL sync error: {get_error_message(e)}",
                exc_info=True,
            )

        # Publish another heartbeat after ACL sync completes
        await self.runtime.state_publisher.publish_progress()
        # Don't fail the entire sync for ACL errors

    async def _finalize_progress_and_trackers(
        self, status: SyncJobStatus, error: Optional[str] = None
    ) -> None:
        """Finalize progress tracking and entity state tracker.

        Args:
            status: The final status of the sync job
            error: Optional error message if the sync failed
        """
        # Publish completion via SyncStatePublisher
        await self.runtime.state_publisher.publish_completion(status, error)

    async def _complete_sync(self) -> None:
        """Mark sync job as completed with final statistics."""
        stats = self.runtime.entity_tracker.get_stats()

        # Save cursor data if it exists (for incremental syncs)
        await self._save_cursor_data()

        # For snapshot sources: update short_name to the original source so that
        # downstream consumers (search, metadata builders) see the real source.
        await self._update_snapshot_short_name()

        await sync_job_service.update_status(
            sync_job_id=self.sync_context.sync_job.id,
            status=SyncJobStatus.COMPLETED,
            ctx=self.sync_context,
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
            ctx=self.sync_context,
            sync_id=self.sync_context.sync.id,
            entities_processed=entities_processed,
            entities_synced=entities_synced,  # NEW parameter
            stats=stats,  # NEW: pass full stats for breakdown
            duration_ms=duration_ms,
        )

        self.sync_context.logger.info(
            f"Completed sync job {self.sync_context.sync_job.id} successfully. Stats: {stats}"
        )

    async def _update_snapshot_short_name(self) -> None:
        """For snapshot sources, update source_connection.short_name to the original source.

        After a successful sync, the snapshot source_connection's short_name is changed
        from "snapshot" to the original source name (e.g., "github", "gmail"). This makes
        the source_connection transparent to downstream consumers (search, metadata builders,
        filters). The original source name is read from the entity's system metadata.

        Re-syncing a completed snapshot is blocked by a guard in SourceBuilder.
        """
        if self.runtime.source.short_name != "snapshot":
            return

        try:
            from sqlalchemy import select as sa_select

            from airweave import crud
            from airweave.models.entity import Entity as EntityModel

            async with get_db_context() as db:
                # Get the original source_name from any synced entity
                result = await db.execute(
                    sa_select(EntityModel.source_name)
                    .where(EntityModel.sync_id == self.sync_context.sync.id)
                    .limit(1)
                )
                original_source_name = result.scalar_one_or_none()

                if not original_source_name or original_source_name == "snapshot":
                    self.sync_context.logger.debug(
                        "[Snapshot] Could not determine original source name, keeping 'snapshot'"
                    )
                    return

                # Update source_connection short_name
                source_connection = await crud.source_connection.get_by_sync_id(
                    db, sync_id=self.sync_context.sync.id, ctx=self.sync_context
                )
                if source_connection:
                    source_connection.short_name = original_source_name
                    await db.commit()
                    self.sync_context.logger.info(
                        f"[Snapshot] Updated source_connection short_name: "
                        f"snapshot → {original_source_name}"
                    )
        except Exception as e:
            # Non-fatal: the metadata builder fallback handles snapshot sources anyway
            self.sync_context.logger.warning(f"[Snapshot] Failed to update short_name: {e}")

    async def _save_cursor_data(self) -> None:
        """Save cursor data to database if it exists."""
        # Check if cursor updates are disabled
        if (
            self.sync_context.execution_config
            and self.sync_context.execution_config.cursor.skip_updates
        ):
            self.sync_context.logger.info("⏭️ Skipping cursor update (disabled by execution_config)")
            return

        if not hasattr(self.sync_context, "cursor") or not self.runtime.cursor.cursor_data:
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
                    cursor_data=self.runtime.cursor.cursor_data,
                    ctx=self.sync_context,
                    cursor_field=self.runtime.cursor.cursor_field,
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

        stats = self.runtime.entity_tracker.get_stats()

        await sync_job_service.update_status(
            sync_job_id=self.sync_context.sync_job.id,
            status=SyncJobStatus.FAILED,
            ctx=self.sync_context,
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
            ctx=self.sync_context,
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
            ctx=self.sync_context,
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
            ctx=self.sync_context,
            source_short_name=self.sync_context.connection.short_name,
            source_connection_id=self.sync_context.connection.id,
            duration_ms=duration_ms,
        )
