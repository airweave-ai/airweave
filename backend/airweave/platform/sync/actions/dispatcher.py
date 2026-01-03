"""Action dispatcher for concurrent handler execution.

Dispatches resolved actions to all registered handlers concurrently,
implementing all-or-nothing semantics where any failure fails the sync.
"""

import asyncio
from typing import TYPE_CHECKING, List

from airweave.platform.sync.actions.types import ActionBatch
from airweave.platform.sync.exceptions import SyncFailureError
from airweave.platform.sync.handlers.postgres import PostgresMetadataHandler
from airweave.platform.sync.handlers.protocol import ActionHandler

if TYPE_CHECKING:
    from airweave.platform.sync.context import SyncContext


class ActionDispatcher:
    """Dispatches actions to all registered handlers concurrently.

    Implements all-or-nothing semantics:
    - Destination handlers (Qdrant, RawData) run concurrently
    - If ANY destination handler fails, SyncFailureError bubbles up
    - PostgreSQL metadata handler runs ONLY AFTER all destination handlers succeed
    - This ensures consistency between vector stores and metadata

    Execution Order:
    1. All destination handlers (non-Postgres) execute concurrently
    2. If all succeed → PostgreSQL metadata handler executes
    3. If any fails → SyncFailureError, no Postgres writes
    """

    def __init__(self, handlers: List[ActionHandler]):
        """Initialize dispatcher with handlers.

        Args:
            handlers: List of handlers to dispatch to (configured at factory time)
                     PostgresMetadataHandler is automatically separated for
                     sequential execution after other handlers.
        """
        # Separate postgres handler from destination handlers
        self._destination_handlers: List[ActionHandler] = []
        self._postgres_handler: PostgresMetadataHandler | None = None

        for handler in handlers:
            if isinstance(handler, PostgresMetadataHandler):
                self._postgres_handler = handler
            else:
                self._destination_handlers.append(handler)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def dispatch(
        self,
        batch: ActionBatch,
        sync_context: "SyncContext",
    ) -> None:
        """Dispatch action batch to all handlers.

        Execution order:
        1. All destination handlers concurrently (Qdrant, RawData, etc.)
        2. If all succeed → PostgreSQL metadata handler
        3. If any fails → SyncFailureError propagates

        Args:
            batch: Resolved and processed action batch (with chunk_entities populated)
            sync_context: Sync context

        Raises:
            SyncFailureError: If any handler fails
        """
        if not batch.has_mutations:
            sync_context.logger.debug("[Dispatcher] No mutations to dispatch")
            return

        handler_names = [h.name for h in self._destination_handlers]
        sync_context.logger.debug(
            f"[Dispatcher] Dispatching {batch.summary()} to handlers: {handler_names}"
        )

        # Step 1: Execute destination handlers concurrently
        await self._dispatch_to_destinations(batch, sync_context)

        # Step 2: Execute postgres handler (only after destinations succeed)
        if self._postgres_handler:
            await self._dispatch_to_postgres(batch, sync_context)

        sync_context.logger.debug("[Dispatcher] All handlers completed successfully")

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
        - PostgresMetadataHandler → postgres DB

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
            f"[Dispatcher] Dispatching orphan cleanup for {len(orphan_entity_ids)} entities "
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
            raise SyncFailureError(f"[Dispatcher] Orphan cleanup failed: {', '.join(failure_msgs)}")

    # -------------------------------------------------------------------------
    # Internal Methods
    # -------------------------------------------------------------------------

    async def _dispatch_to_destinations(
        self,
        batch: ActionBatch,
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
            failure_msgs = [f"{name}: {err}" for name, err in failures]
            sync_context.logger.error(f"[Dispatcher] Handler failures: {failure_msgs}")
            raise SyncFailureError(f"[Dispatcher] Handler(s) failed: {', '.join(failure_msgs)}")

    async def _dispatch_to_postgres(
        self,
        batch: ActionBatch,
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
            sync_context.logger.error(f"[Dispatcher] PostgreSQL handler failed: {e}", exc_info=True)
            raise SyncFailureError(f"[Dispatcher] PostgreSQL failed: {e}")

    async def _dispatch_to_handler(
        self,
        handler: ActionHandler,
        batch: ActionBatch,
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
                f"[Dispatcher] Handler {handler.name} failed: {e}", exc_info=True
            )
            raise SyncFailureError(f"Handler {handler.name} failed: {e}")

    async def _dispatch_orphan_to_handler(
        self,
        handler: ActionHandler,
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
                f"[Dispatcher] Handler {handler.name} orphan cleanup failed: {e}",
                exc_info=True,
            )
            raise SyncFailureError(f"Handler {handler.name} orphan cleanup failed: {e}")
