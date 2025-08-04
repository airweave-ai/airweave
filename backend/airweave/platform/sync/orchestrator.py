"""Module for data synchronization with improved architecture."""

import asyncio
from typing import Optional

from airweave import schemas
from airweave.core.datetime_utils import utc_now_naive
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
        self.stream_buffer_size = 100

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

    async def _start_sync(self) -> None:
        """Initialize sync job and update status to in-progress."""
        self.sync_context.logger.info(
            f"Starting sync job {self.sync_context.sync_job.id} for sync "
            f"{self.sync_context.sync.id}"
        )

        await sync_job_service.update_status(
            sync_job_id=self.sync_context.sync_job.id,
            status=SyncJobStatus.IN_PROGRESS,
            auth_context=self.sync_context.auth_context,
            started_at=utc_now_naive(),
        )

    async def _process_entities(self) -> None:
        """Process entities with pull-based concurrency control.

        Only pulls an entity from the stream when a worker is available,
        ensuring natural backpressure throughout the pipeline.
        """
        source_node = self.sync_context.dag.get_source_node()

        self.sync_context.logger.info(
            f"Starting pull-based processing from source {self.sync_context.source._name} "
            f"(buffer: {self.stream_buffer_size}, max workers: {self.worker_pool.max_workers})"
        )

        stream_error: Optional[Exception] = None
        pending_tasks: set[asyncio.Task] = set()

        try:
            async with AsyncSourceStream(
                self.sync_context.source.generate_entities(),
                queue_size=self.stream_buffer_size,
                logger=self.sync_context.logger,
            ) as stream:
                async for entity in stream.get_entities():
                    # Handle skipped entities without using a worker
                    if getattr(entity, "should_skip", False):
                        self.sync_context.logger.debug(f"Skipping entity: {entity.entity_id}")
                        await self.sync_context.progress.increment("skipped")
                        continue

                    # Submit entity processing to worker pool
                    # This creates a task that runs concurrently with others
                    task = await self.worker_pool.submit(
                        self.entity_processor.process,
                        entity=entity,
                        source_node=source_node,
                        sync_context=self.sync_context,
                    )
                    pending_tasks.add(task)

                    # Clean up completed tasks periodically to avoid memory buildup
                    if len(pending_tasks) >= self.worker_pool.max_workers:
                        pending_tasks = await self._handle_completed_tasks(pending_tasks)

        except Exception as e:
            stream_error = e
            self.sync_context.logger.error(f"Error during entity streaming: {get_error_message(e)}")
            # Cancel all pending tasks
            for task in pending_tasks:
                task.cancel()
            raise

        finally:
            # Wait for all remaining tasks to complete
            await self._wait_for_remaining_tasks(pending_tasks)
            await self.sync_context.progress.finalize(is_complete=(stream_error is None))

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
            self.sync_context.logger.info(
                f"Waiting for {len(pending_tasks)} remaining tasks to complete"
            )
            done, _ = await asyncio.wait(pending_tasks)
            # Check for exceptions in completed tasks
            for task in done:
                if not task.cancelled() and task.exception():
                    self.sync_context.logger.error(
                        f"Task failed with exception: {task.exception()}"
                    )

    async def _complete_sync(self) -> None:
        """Mark sync job as completed with final statistics."""
        stats = getattr(self.sync_context.progress, "stats", None)

        # Save cursor data if it exists (for incremental syncs)
        await self._save_cursor_data()

        await sync_job_service.update_status(
            sync_job_id=self.sync_context.sync_job.id,
            status=SyncJobStatus.COMPLETED,
            auth_context=self.sync_context.auth_context,
            completed_at=utc_now_naive(),
            stats=stats,
        )

        self.sync_context.logger.info(
            f"Completed sync job {self.sync_context.sync_job.id} successfully. Stats: {stats}"
        )

    async def _save_cursor_data(self) -> None:
        """Save cursor data to database if it exists (for incremental syncs)."""
        if not hasattr(self.sync_context, "cursor") or not self.sync_context.cursor.cursor_data:
            return

        try:
            async with get_db_context() as db:
                await sync_cursor_service.create_or_update_cursor(
                    db=db,
                    sync_id=self.sync_context.sync.id,
                    cursor_data=self.sync_context.cursor.cursor_data,
                    auth_context=self.sync_context.auth_context,
                )
                self.sync_context.logger.info(
                    f"Saved cursor data for sync {self.sync_context.sync.id}"
                )
        except Exception as e:
            self.sync_context.logger.warning(
                f"Failed to save cursor data for sync {self.sync_context.sync.id}: {e}"
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
            auth_context=self.sync_context.auth_context,
            error=error_message,
            failed_at=utc_now_naive(),
            stats=stats,
        )
