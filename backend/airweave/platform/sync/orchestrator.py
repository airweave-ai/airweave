"""Module for data synchronization with improved architecture."""

from datetime import datetime
from typing import Optional

from airweave import schemas
from airweave.core.shared_models import SyncJobStatus
from airweave.core.sync_job_service import sync_job_service
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sync.context import SyncContext
from airweave.platform.sync.entity_processor import EntityProcessor
from airweave.platform.sync.stream import AsyncSourceStream
from airweave.platform.sync.worker_pool import AsyncWorkerPool


class SyncOrchestrator:
    """Orchestrates data synchronization from sources to destinations.

    Uses a hybrid approach that allows limited pending tasks (2x workers)
    to handle both fast and slow sources efficiently.
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

        # Increased queue size for better buffering of fast sources
        self.stream_buffer_size = 100

        # Allow up to 2x workers as pending tasks
        # This provides good performance for fast sources while limiting memory usage
        self.max_pending_factor = 2.0

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
            current_user=self.sync_context.current_user,
            started_at=datetime.now(),
        )

    async def _process_entities(self) -> None:
        """Process entities from source with limited pending tasks.

        Uses a hybrid approach:
        - AsyncSourceStream queue (100) for read-ahead buffering
        - Limited pending tasks (2x workers) to prevent memory issues
        - Throttling when approaching the pending task limit
        """
        source_node = self.sync_context.dag.get_source_node()

        self.sync_context.logger.info(
            f"Starting entity stream processing from source {self.sync_context.source._name} "
            f"(buffer: {self.stream_buffer_size}, max pending: "
            f"{int(self.worker_pool.max_workers * self.max_pending_factor)})"
        )

        # Track any errors that occur during streaming
        stream_error: Optional[Exception] = None

        try:
            async with AsyncSourceStream(
                self.sync_context.source.generate_entities(),
                queue_size=self.stream_buffer_size,
                logger=self.sync_context.logger,
            ) as stream:
                async for entity in stream.get_entities():
                    await self._process_entity_with_throttling(entity, source_node)

        except Exception as e:
            stream_error = e
            self.sync_context.logger.error(f"Error during entity streaming: {e}")
            raise

        finally:
            # Wait for all submitted tasks to complete
            await self.worker_pool.wait_for_completion()

            # Finalize progress tracking
            await self.sync_context.progress.finalize(is_complete=(stream_error is None))

    async def _process_entity_with_throttling(self, entity: BaseEntity, source_node) -> None:
        """Process entity with throttling based on pending tasks.

        Implements intelligent throttling to prevent too many pending tasks
        while allowing enough buffering for fast sources.

        Args:
            entity: The entity to process
            source_node: The source node from the DAG
        """
        # Handle skipped entities
        if getattr(entity, "should_skip", False):
            self.sync_context.logger.debug(f"Skipping entity: {entity.entity_id}")
            await self.sync_context.progress.increment("skipped")
            return

        # Apply throttling if needed
        await self._apply_throttling()

        # Submit entity for processing
        await self.worker_pool.submit(
            self.entity_processor.process,
            entity=entity,
            source_node=source_node,
            sync_context=self.sync_context,
        )

    async def _apply_throttling(self) -> None:
        """Throttle submission if too many tasks are pending.

        Allows up to 2x workers as pending tasks to balance between:
        - Fast sources: Can build up some backlog for efficiency
        - Slow sources: Won't accumulate many pending tasks anyway
        - Memory usage: Limited to reasonable bounds
        """
        pending_count = len(self.worker_pool.pending_tasks)
        max_workers = self.worker_pool.max_workers
        max_pending = int(max_workers * self.max_pending_factor)

        # If we're at or above the limit, wait for some tasks to complete
        if pending_count >= max_pending:
            self.sync_context.logger.debug(
                f"Throttling: {pending_count} pending tasks at limit of {max_pending}. "
                f"Waiting for tasks to complete."
            )

            # Wait until we're below 90% of max to avoid constant throttling
            target_pending = int(max_pending * 0.9)
            while len(self.worker_pool.pending_tasks) > target_pending:
                await self.worker_pool.wait_for_batch(timeout=0.5)

            self.sync_context.logger.debug(
                f"Throttling released: {len(self.worker_pool.pending_tasks)} pending tasks"
            )

    async def _complete_sync(self) -> None:
        """Mark sync job as completed with final statistics."""
        stats = getattr(self.sync_context.progress, "stats", None)

        await sync_job_service.update_status(
            sync_job_id=self.sync_context.sync_job.id,
            status=SyncJobStatus.COMPLETED,
            current_user=self.sync_context.current_user,
            completed_at=datetime.now(),
            stats=stats,
        )

        self.sync_context.logger.info(
            f"Completed sync job {self.sync_context.sync_job.id} successfully. Stats: {stats}"
        )

    async def _handle_sync_failure(self, error: Exception) -> None:
        """Handle sync failure by updating job status with error details."""
        self.sync_context.logger.error(
            f"Sync job {self.sync_context.sync_job.id} failed: {error}", exc_info=True
        )

        stats = getattr(self.sync_context.progress, "stats", None)

        await sync_job_service.update_status(
            sync_job_id=self.sync_context.sync_job.id,
            status=SyncJobStatus.FAILED,
            current_user=self.sync_context.current_user,
            error=str(error),
            failed_at=datetime.now(),
            stats=stats,
        )
