"""Destination handler for the sync pipeline.

Processes entities via ChunkEmbedProcessor and inserts into destinations
with retry logic and soft-fail support.
"""

import asyncio
from typing import TYPE_CHECKING, Awaitable, Callable, List

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
from airweave.platform.sync.processors import ChunkEmbedProcessor

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext
    from airweave.platform.contexts.runtime import SyncRuntime
    from airweave.platform.entities import BaseEntity


_processor = ChunkEmbedProcessor()

_RETRYABLE_EXCEPTIONS: tuple = (
    ConnectionError,
    TimeoutError,
    httpx.NetworkError,
    httpx.TimeoutException,
    httpcore.NetworkError,
    httpcore.TimeoutException,
)


class DestinationHandler(EntityActionHandler):
    """Handler that chunks/embeds entities and inserts into destinations."""

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
        runtime: "SyncRuntime",
    ) -> None:
        """Handle batch by processing and dispatching to each destination."""
        if not self._destinations:
            sync_context.logger.debug(f"[{self.name}] No destinations, skipping")
            return

        if not batch.has_mutations:
            sync_context.logger.debug(f"[{self.name}] No mutations, skipping")
            return

        if batch.updates:
            await self._do_delete_by_ids(
                [a.entity_id for a in batch.updates],
                "update_delete",
                sync_context,
            )

        entities = batch.get_entities_to_process()
        if entities:
            await self._do_process_and_insert(entities, sync_context, runtime)

        if batch.deletes:
            await self.handle_deletes(batch.deletes, sync_context)

    async def handle_inserts(
        self,
        actions: List[EntityInsertAction],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> None:
        """Handle inserts - process and insert to destinations."""
        if not actions:
            return
        entities = [a.entity for a in actions]
        sync_context.logger.debug(f"[{self.name}] Inserting {len(entities)} entities")
        await self._do_process_and_insert(entities, sync_context, runtime)

    async def handle_updates(
        self,
        actions: List[EntityUpdateAction],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> None:
        """Handle updates - delete old, then insert new."""
        if not actions:
            return
        entity_ids = [a.entity_id for a in actions]
        entities = [a.entity for a in actions]
        sync_context.logger.debug(f"[{self.name}] Updating {len(entities)} entities")
        await self._do_delete_by_ids(entity_ids, "update_delete", sync_context)
        await self._do_process_and_insert(entities, sync_context, runtime)

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
        runtime: "SyncRuntime",
    ) -> None:
        """Process entities through ChunkEmbedProcessor and insert into destinations."""
        copies = [e.model_copy(deep=True) for e in entities]
        proc_start = asyncio.get_running_loop().time()
        processed = await _processor.process(copies, sync_context, runtime)
        proc_elapsed = asyncio.get_running_loop().time() - proc_start
        if proc_elapsed > 10:
            sync_context.logger.warning(
                f"[{self.name}] ChunkEmbedProcessor slow: "
                f"{proc_elapsed:.1f}s for {len(entities)} entities"
            )

        if not processed:
            sync_context.logger.debug(f"[{self.name}] No entities after processing")
            return

        for dest in self._destinations:
            await self._execute_with_retry(
                operation=lambda d=dest, p=processed: d.bulk_insert(p),
                operation_name=f"insert_{dest.__class__.__name__}",
                destination=dest,
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
                destination=dest,
                sync_context=sync_context,
            )

    # -------------------------------------------------------------------------
    # Private: Helpers
    # -------------------------------------------------------------------------

    async def _execute_with_retry(
        self,
        operation: Callable[[], Awaitable],
        operation_name: str,
        destination: BaseDestination,
        sync_context: "SyncContext",
        max_retries: int = 4,
    ) -> None:
        """Execute operation with exponential backoff retry for network issues."""
        for attempt in range(max_retries + 1):
            try:
                start = asyncio.get_running_loop().time()
                result = await operation()
                elapsed = asyncio.get_running_loop().time() - start
                if elapsed > 10:
                    sync_context.logger.warning(
                        f"[{self.name}] {operation_name} slow: {elapsed:.1f}s "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )
                return result
            except _RETRYABLE_EXCEPTIONS as e:
                error_msg = str(e) or "(empty error message)"
                if attempt < max_retries:
                    wait = 2 * (2**attempt)
                    sync_context.logger.warning(
                        f"[{self.name}] {operation_name} failed (attempt {attempt + 1}): "
                        f"{type(e).__name__}: {error_msg}. Retrying in {wait}s..."
                    )
                    await asyncio.sleep(wait)
                else:
                    if destination.soft_fail:
                        retries = max_retries + 1
                        sync_context.logger.error(
                            f"🔴 [{self.name}] {operation_name} SOFT-FAIL after {retries} "
                            f"attempts: {type(e).__name__}: {error_msg}. (soft_fail=True)",
                            exc_info=True,
                        )
                        return
                    raise SyncFailureError(
                        f"Destination unavailable: {type(e).__name__}: {error_msg}"
                    ) from e
            except Exception as e:
                error_msg = str(e) or "(empty error message)"
                if destination.soft_fail:
                    sync_context.logger.error(
                        f"🔴 [{self.name}] {operation_name} SOFT-FAIL: "
                        f"{type(e).__name__}: {error_msg}. Sync continues (soft_fail=True)",
                        exc_info=True,
                    )
                    return

                sync_context.logger.error(
                    f"[{self.name}] {operation_name} failed: {type(e).__name__}: {error_msg}",
                    exc_info=True,
                )
                raise SyncFailureError(
                    f"Destination failed: {type(e).__name__}: {error_msg}"
                ) from e
