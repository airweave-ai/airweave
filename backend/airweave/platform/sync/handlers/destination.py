"""Unified destination handler using processor strategy pattern.

Destinations declare what they need via processing_requirement class var.
Handler owns processor lifecycle (singletons).
"""

import asyncio
from typing import TYPE_CHECKING, Awaitable, Callable, Dict, List

import httpcore
import httpx

from airweave.platform.destinations._base import BaseDestination
from airweave.platform.sync.actions.entity.types import (
    EntityActionBatch,
    EntityDeleteAction,
    EntityInsertAction,
    EntityUpdateAction,
)
from airweave.platform.sync.exceptions import SyncFailureError
from airweave.platform.sync.handlers.protocol import EntityActionHandler
from airweave.platform.sync.pipeline import ProcessingRequirement
from airweave.platform.sync.processors import (
    ContentProcessor,
    QdrantChunkEmbedProcessor,
    RawProcessor,
    TextOnlyProcessor,
    VespaChunkEmbedProcessor,
)

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext
    from airweave.platform.entities import BaseEntity


# Singleton processors - stateless, reusable
_PROCESSORS: Dict[ProcessingRequirement, ContentProcessor] = {
    ProcessingRequirement.CHUNKS_AND_EMBEDDINGS: QdrantChunkEmbedProcessor(),
    ProcessingRequirement.VESPA_CHUNKS_AND_EMBEDDINGS: VespaChunkEmbedProcessor(),
    ProcessingRequirement.TEXT_ONLY: TextOnlyProcessor(),
    ProcessingRequirement.RAW: RawProcessor(),
}

# Retryable network exceptions
_RETRYABLE_EXCEPTIONS: tuple = (
    ConnectionError,
    TimeoutError,
    httpx.NetworkError,
    httpx.TimeoutException,
    httpcore.NetworkError,
    httpcore.TimeoutException,
)


class DestinationHandler(EntityActionHandler):
    """Generic handler that maps ProcessingRequirement to processors.

    Destinations declare what they need via processing_requirement class var.
    Handler maps requirements to processor instances (singletons).
    """

    def __init__(self, destinations: List[BaseDestination]):
        """Initialize handler with destinations."""
        self._destinations = destinations

    @property
    def name(self) -> str:
        """Handler name for logging."""
        if not self._destinations:
            return "destination[]"
        names = [d.__class__.__name__ for d in self._destinations]
        return f"destination[{','.join(names)}]"

    # -------------------------------------------------------------------------
    # Protocol: Public Interface
    # -------------------------------------------------------------------------

    async def handle_batch(
        self,
        batch: EntityActionBatch,
        sync_context: "SyncContext",
    ) -> None:
        """Handle batch by processing and dispatching to each destination."""
        if not self._destinations:
            sync_context.logger.debug(f"[{self.name}] No destinations, skipping")
            return

        if not batch.has_mutations:
            sync_context.logger.debug(f"[{self.name}] No mutations, skipping")
            return

        # Updates: delete old data first, then insert new
        if batch.updates:
            await self._do_delete_by_ids(
                [a.entity_id for a in batch.updates],
                "update_delete",
                sync_context,
            )

        # Process and insert (inserts + updates)
        entities = batch.get_entities_to_process()
        if entities:
            await self._do_process_and_insert(entities, sync_context)

        # Deletes
        if batch.deletes:
            await self.handle_deletes(batch.deletes, sync_context)

    async def handle_inserts(
        self,
        actions: List[EntityInsertAction],
        sync_context: "SyncContext",
    ) -> None:
        """Handle inserts - process and insert to destinations."""
        if not actions:
            return
        entities = [a.entity for a in actions]
        sync_context.logger.debug(f"[{self.name}] Inserting {len(entities)} entities")
        await self._do_process_and_insert(entities, sync_context)

    async def handle_updates(
        self,
        actions: List[EntityUpdateAction],
        sync_context: "SyncContext",
    ) -> None:
        """Handle updates - delete old, then insert new."""
        if not actions:
            return
        entity_ids = [a.entity_id for a in actions]
        entities = [a.entity for a in actions]
        sync_context.logger.debug(f"[{self.name}] Updating {len(entities)} entities")
        # Delete old data first
        await self._do_delete_by_ids(entity_ids, "update_delete", sync_context)
        # Insert new data
        await self._do_process_and_insert(entities, sync_context)

    async def handle_deletes(
        self,
        actions: List[EntityDeleteAction],
        sync_context: "SyncContext",
    ) -> None:
        """Handle deletes - remove from all destinations."""
        if not actions:
            return
        entity_ids = [a.entity_id for a in actions]
        sync_context.logger.debug(f"[{self.name}] Deleting {len(entity_ids)} entities")
        await self._do_delete_by_ids(entity_ids, "delete", sync_context)

    async def handle_orphan_cleanup(
        self,
        orphan_entity_ids: List[str],
        sync_context: "SyncContext",
    ) -> None:
        """Clean up orphaned entities from all destinations."""
        if not orphan_entity_ids:
            return
        sync_context.logger.debug(f"[{self.name}] Cleaning {len(orphan_entity_ids)} orphans")
        await self._do_delete_by_ids(orphan_entity_ids, "orphan_cleanup", sync_context)

    # -------------------------------------------------------------------------
    # Private: Core Operations
    # -------------------------------------------------------------------------

    async def _do_process_and_insert(
        self,
        entities: List["BaseEntity"],
        sync_context: "SyncContext",
    ) -> None:
        """Process entities and insert into each destination.

        Each destination gets entities processed by its required processor.
        Deep-copies entities to avoid cross-contamination between processors.
        """
        for dest in self._destinations:
            processor = self._get_processor(dest)

            # Deep-copy to avoid cross-contamination
            dest_entities = [e.model_copy(deep=True) for e in entities]
            processed = await processor.process(dest_entities, sync_context)

            if not processed:
                sync_context.logger.debug(
                    f"[{self.name}] No entities after {processor.__class__.__name__}"
                )
                continue

            await self._execute_with_retry(
                operation=lambda d=dest, p=processed: d.bulk_insert(p),
                operation_name=f"insert_{dest.__class__.__name__}",
                sync_context=sync_context,
            )

    async def _do_delete_by_ids(
        self,
        entity_ids: List[str],
        operation: str,
        sync_context: "SyncContext",
    ) -> None:
        """Delete entities by parent IDs from all destinations."""
        for dest in self._destinations:
            await self._execute_with_retry(
                operation=lambda d=dest, ids=entity_ids: d.bulk_delete_by_parent_ids(
                    ids, sync_context.sync.id
                ),
                operation_name=f"{operation}_{dest.__class__.__name__}",
                sync_context=sync_context,
            )

    # -------------------------------------------------------------------------
    # Private: Helpers
    # -------------------------------------------------------------------------

    def _get_processor(self, dest: BaseDestination) -> ContentProcessor:
        """Get processor for a destination based on its processing_requirement."""
        requirement = dest.processing_requirement
        processor = _PROCESSORS.get(requirement)
        if processor is None:
            raise ValueError(
                f"Unknown ProcessingRequirement: {requirement} for {dest.__class__.__name__}"
            )
        return processor

    async def _execute_with_retry(
        self,
        operation: Callable[[], Awaitable],
        operation_name: str,
        sync_context: "SyncContext",
        max_retries: int = 4,
    ) -> None:
        """Execute operation with exponential backoff retry for network issues."""
        for attempt in range(max_retries + 1):
            try:
                return await operation()
            except _RETRYABLE_EXCEPTIONS as e:
                if attempt < max_retries:
                    wait = 2 * (2**attempt)
                    sync_context.logger.warning(
                        f"[{self.name}] {operation_name} failed (attempt {attempt + 1}): "
                        f"{type(e).__name__}: {e}. Retrying in {wait}s..."
                    )
                    await asyncio.sleep(wait)
                else:
                    raise SyncFailureError(
                        f"Destination unavailable: {type(e).__name__}: {e}"
                    ) from e
            except Exception as e:
                sync_context.logger.error(
                    f"[{self.name}] {operation_name} failed: {type(e).__name__}: {e}"
                )
                raise SyncFailureError(f"Destination failed: {type(e).__name__}: {e}") from e
