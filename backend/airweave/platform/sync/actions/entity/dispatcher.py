"""Action dispatcher for concurrent handler execution.

Dispatches resolved entity actions to all registered handlers concurrently,
implementing all-or-nothing semantics where any failure fails the sync.
"""

import asyncio
from typing import TYPE_CHECKING, List

from airweave.platform.sync.actions.entity.types import EntityActionBatch
from airweave.platform.sync.exceptions import SyncFailureError
from airweave.platform.sync.handlers.entity_postgres import EntityPostgresHandler
from airweave.platform.sync.handlers.protocol import EntityActionHandler

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext


class EntityActionDispatcher:
    """Dispatches entity actions to all registered handlers concurrently.

    Implements all-or-nothing semantics:
    - Destination handlers (Qdrant, RawData) run concurrently
    - If ANY destination handler fails, SyncFailureError bubbles up
    - PostgreSQL metadata handler runs ONLY AFTER all destination handlers succeed
    - This ensures consistency between vector stores and metadata

    Collection-Level Deduplication:
    - Inserts with skip_content_handlers=True are filtered out for destination handlers
    - PostgreSQL handler receives ALL inserts (needs to record entity ownership)
    - Filtering happens centrally in dispatcher, not in individual handlers

    Execution Order:
    1. All destination handlers (non-Postgres) execute concurrently (filtered batch)
    2. If all succeed → PostgreSQL metadata handler executes (full batch)
    3. If any fails → SyncFailureError, no Postgres writes
    """

    def __init__(self, handlers: List[EntityActionHandler]):
        """Initialize dispatcher with handlers.

        Args:
            handlers: List of handlers to dispatch to (configured at factory time)
                     EntityPostgresHandler is automatically separated for
                     sequential execution after other handlers.
        """
        # Separate postgres handler from destination handlers
        self._destination_handlers: List[EntityActionHandler] = []
        self._postgres_handler: EntityPostgresHandler | None = None

        for handler in handlers:
            if isinstance(handler, EntityPostgresHandler):
                self._postgres_handler = handler
            else:
                self._destination_handlers.append(handler)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def dispatch(
        self,
        batch: EntityActionBatch,
        sync_context: "SyncContext",
    ) -> None:
        """Dispatch action batch to all handlers.

        Execution order:
        1. All destination handlers concurrently (filtered batch - skip_content_handlers removed)
        2. If all succeed → PostgreSQL metadata handler (full batch - all inserts)
        3. If any fails → SyncFailureError propagates

        Args:
            batch: Resolved and processed action batch (with chunk_entities populated)
            sync_context: Sync context

        Raises:
            SyncFailureError: If any handler fails
        """
        if not batch.has_mutations:
            sync_context.logger.debug("[EntityDispatcher] No mutations to dispatch")
            return

        handler_names = [h.name for h in self._destination_handlers]
        sync_context.logger.debug(
            f"[EntityDispatcher] Dispatching {batch.summary()} to handlers: {handler_names}"
        )

        # Step 1: Create filtered batch for destination handlers (collection-level dedup)
        destination_batch = self._filter_batch_for_destinations(batch, sync_context)

        # Step 2: Execute destination handlers concurrently with filtered batch
        await self._dispatch_to_destinations(destination_batch, sync_context)

        # Step 3: Execute postgres handler with FULL batch (needs all inserts for ownership)
        if self._postgres_handler:
            await self._dispatch_to_postgres(batch, sync_context)

        sync_context.logger.debug("[EntityDispatcher] All handlers completed successfully")

    async def dispatch_orphan_cleanup(
        self,
        orphan_entity_ids: List[str],
        sync_context: "SyncContext",
    ) -> None:
        """Dispatch orphan cleanup to ALL handlers concurrently.

        Called at the end of sync for entities that exist in DB but were not
        encountered during this sync run.

        Each handler independently cleans up its own storage:
        - DestinationHandler → vector stores (Qdrant, Vespa)
        - ArfHandler → ARF storage
        - EntityPostgresHandler → postgres DB

        Args:
            orphan_entity_ids: Entity IDs to clean up
            sync_context: Sync context

        Raises:
            SyncFailureError: If any handler fails cleanup
        """
        if not orphan_entity_ids:
            return

        # Collect ALL handlers
        all_handlers = list(self._destination_handlers)
        if self._postgres_handler:
            all_handlers.append(self._postgres_handler)

        if not all_handlers:
            return

        sync_context.logger.info(
            f"[EntityDispatcher] Dispatching orphan cleanup for {len(orphan_entity_ids)} entities "
            f"to {len(all_handlers)} handlers"
        )

        # Execute all handlers concurrently
        tasks = [
            asyncio.create_task(
                self._dispatch_orphan_to_handler(handler, orphan_entity_ids, sync_context),
                name=f"orphan-{handler.name}",
            )
            for handler in all_handlers
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check for failures
        failures = []
        for handler, result in zip(all_handlers, results, strict=False):
            if isinstance(result, Exception):
                failures.append((handler.name, result))

        if failures:
            failure_msgs = [f"{name}: {err}" for name, err in failures]
            raise SyncFailureError(
                f"[EntityDispatcher] Orphan cleanup failed: {', '.join(failure_msgs)}"
            )

    # -------------------------------------------------------------------------
    # Internal Methods
    # -------------------------------------------------------------------------

    def _filter_batch_for_destinations(
        self,
        batch: EntityActionBatch,
        sync_context: "SyncContext",
    ) -> EntityActionBatch:
        """Filter batch for destination handlers (collection-level deduplication).

        Removes inserts with skip_content_handlers=True. These entities already
        exist in another sync within the collection with the same hash, so we
        don't need to write them to vector DBs or ARF again.

        Args:
            batch: Original batch with all inserts
            sync_context: Sync context for logging

        Returns:
            Filtered batch for destination handlers
        """
        # Filter out inserts where skip_content_handlers=True
        filtered_inserts = [a for a in batch.inserts if not a.skip_content_handlers]
        skipped_count = len(batch.inserts) - len(filtered_inserts)

        if skipped_count > 0:
            sync_context.logger.debug(
                f"[EntityDispatcher] Filtering {skipped_count} inserts for destination handlers "
                f"(collection-level dedup)"
            )

        # If no filtering needed, return original batch
        if skipped_count == 0:
            return batch

        # Create new batch with filtered inserts
        return EntityActionBatch(
            inserts=filtered_inserts,
            updates=batch.updates,
            deletes=batch.deletes,
            keeps=batch.keeps,
            existing_map=batch.existing_map,
        )

    async def _dispatch_to_destinations(
        self,
        batch: EntityActionBatch,
        sync_context: "SyncContext",
    ) -> None:
        """Dispatch to all destination handlers concurrently.

        Args:
            batch: Action batch
            sync_context: Sync context

        Raises:
            SyncFailureError: If any destination handler fails
        """
        if not self._destination_handlers:
            return

        # Create tasks for all destination handlers
        tasks = [
            asyncio.create_task(
                self._dispatch_to_handler(handler, batch, sync_context),
                name=f"handler-{handler.name}",
            )
            for handler in self._destination_handlers
        ]

        # Wait for all - if any fails, collect errors
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check for failures
        failures = []
        for handler, result in zip(self._destination_handlers, results, strict=False):
            if isinstance(result, Exception):
                failures.append((handler.name, result))

        if failures:
            failure_msgs = [f"{name}: {type(err).__name__}: {err}" for name, err in failures]
            sync_context.logger.error(f"[EntityDispatcher] Handler failures: {failure_msgs}")
            raise SyncFailureError(
                f"[EntityDispatcher] Handler(s) failed: {', '.join(failure_msgs)}"
            )

    async def _dispatch_to_postgres(
        self,
        batch: EntityActionBatch,
        sync_context: "SyncContext",
    ) -> None:
        """Dispatch to PostgreSQL metadata handler (after destinations succeed).

        Args:
            batch: Action batch
            sync_context: Sync context

        Raises:
            SyncFailureError: If postgres handler fails
        """
        try:
            await self._postgres_handler.handle_batch(batch, sync_context)
        except SyncFailureError:
            raise
        except Exception as e:
            sync_context.logger.error(
                f"[EntityDispatcher] PostgreSQL handler failed: {e}", exc_info=True
            )
            raise SyncFailureError(f"[EntityDispatcher] PostgreSQL failed: {e}")

    async def _dispatch_to_handler(
        self,
        handler: EntityActionHandler,
        batch: EntityActionBatch,
        sync_context: "SyncContext",
    ) -> None:
        """Dispatch to single handler with error wrapping.

        Args:
            handler: Handler to dispatch to
            batch: Action batch
            sync_context: Sync context

        Raises:
            SyncFailureError: If handler fails
        """
        try:
            await handler.handle_batch(batch, sync_context)
        except SyncFailureError:
            raise
        except Exception as e:
            sync_context.logger.error(
                f"[EntityDispatcher] Handler {handler.name} failed: {e}", exc_info=True
            )
            raise SyncFailureError(f"Handler {handler.name} failed: {e}")

    async def _dispatch_orphan_to_handler(
        self,
        handler: EntityActionHandler,
        orphan_entity_ids: List[str],
        sync_context: "SyncContext",
    ) -> None:
        """Dispatch orphan cleanup to single handler.

        Args:
            handler: Handler to dispatch to
            orphan_entity_ids: Entity IDs to clean up
            sync_context: Sync context

        Raises:
            SyncFailureError: If handler fails
        """
        try:
            await handler.handle_orphan_cleanup(orphan_entity_ids, sync_context)
        except SyncFailureError:
            raise
        except Exception as e:
            sync_context.logger.error(
                f"[EntityDispatcher] Handler {handler.name} orphan cleanup failed: {e}",
                exc_info=True,
            )
            raise SyncFailureError(f"Handler {handler.name} orphan cleanup failed: {e}")
