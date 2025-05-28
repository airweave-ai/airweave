"""Module for data synchronization with improved architecture."""

from datetime import datetime

from airweave import schemas
from airweave.core.shared_models import SyncJobStatus
from airweave.core.sync_job_service import sync_job_service
from airweave.db.session import get_db_context
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sync.context import SyncContext
from airweave.platform.sync.entity_processor import EntityProcessor
from airweave.platform.sync.stream import AsyncSourceStream
from airweave.platform.sync.worker_pool import AsyncWorkerPool


# Refactored Orchestrator
class SyncOrchestrator:
    """Main service for data synchronization with improved architecture."""

    def __init__(
        self,
        entity_processor: EntityProcessor,
        worker_pool: AsyncWorkerPool,
        sync_context: SyncContext,
    ):
        """Initialize the sync orchestrator with provided components.

        Args:
            entity_processor: The entity processor to use
            worker_pool: The worker pool to use
            sync_context: The sync context with all required resources
        """
        self.worker_pool = worker_pool
        self.entity_processor = entity_processor
        self.sync_context = sync_context

    async def run(self) -> schemas.Sync:
        """Run a sync with full async processing."""
        try:
            self.sync_context.logger.info(
                f"Starting sync job {self.sync_context.sync_job.id} for sync "
                f"{self.sync_context.sync.id}"
            )

            # Mark job as started
            await sync_job_service.update_status(
                sync_job_id=self.sync_context.sync_job.id,
                status=SyncJobStatus.IN_PROGRESS,
                current_user=self.sync_context.current_user,
                started_at=datetime.now(),
            )

            # Get source node from DAG
            source_node = self.sync_context.dag.get_source_node()

            # Process entity stream
            await self._process_entity_stream(source_node)

            # Use sync_job_service to update job status
            await sync_job_service.update_status(
                sync_job_id=self.sync_context.sync_job.id,
                status=SyncJobStatus.COMPLETED,
                current_user=self.sync_context.current_user,
                completed_at=datetime.now(),
                stats=(
                    self.sync_context.progress.stats
                    if hasattr(self.sync_context.progress, "stats")
                    else None
                ),
            )

            self.sync_context.logger.info(
                f"Completed sync job {self.sync_context.sync_job.id} successfully"
            )
            return self.sync_context.sync

        except Exception as e:
            self.sync_context.logger.error(f"Error during sync: {e}")

            # Use sync_job_service to update job status
            await sync_job_service.update_status(
                sync_job_id=self.sync_context.sync_job.id,
                status=SyncJobStatus.FAILED,
                current_user=self.sync_context.current_user,
                error=str(e),
                failed_at=datetime.now(),
                stats=(
                    self.sync_context.progress.stats
                    if hasattr(self.sync_context.progress, "stats")
                    else None
                ),
            )

            raise

    async def _process_entity_stream(self, source_node) -> None:
        """Process stream of entities from source."""
        error_occurred = False

        self.sync_context.logger.info(
            f"Starting entity stream processing from source {self.sync_context.source._name}"
        )

        # Use the stream as a context manager
        async with AsyncSourceStream(
            self.sync_context.source.generate_entities(), logger=self.sync_context.logger
        ) as stream:
            try:
                # Process entities as they come
                async for entity in stream.get_entities():
                    if getattr(entity, "should_skip", False):
                        await self.sync_context.progress.increment("skipped")
                        continue  # Do not process further

                    # Submit each entity for processing in the worker pool
                    task = await self.worker_pool.submit(
                        self._process_single_entity,
                        entity=entity,
                        source_node=source_node,
                    )

                    # Pythonic way to save entity for error reporting
                    task.entity = entity

                    # If we have too many pending tasks, wait for some to complete
                    if len(self.worker_pool.pending_tasks) >= self.worker_pool.max_workers * 2:
                        await self.worker_pool.wait_for_batch(timeout=0.5)

                # Wait for all remaining tasks
                await self.worker_pool.wait_for_completion()
                self.sync_context.logger.info("All entity processing tasks completed")

            except Exception as e:
                self.sync_context.logger.error(f"Error during entity stream processing: {e}")
                error_occurred = True
                raise
            finally:
                # Finalize progress
                await self.sync_context.progress.finalize(is_complete=not error_occurred)

    async def _process_single_entity(self, entity: BaseEntity, source_node) -> None:
        """Process a single entity through the pipeline."""
        # Create a new database session scope for this task
        async with get_db_context() as db:
            # Process the entity through the pipeline
            await self.entity_processor.process(
                entity=entity, source_node=source_node, sync_context=self.sync_context, db=db
            )
