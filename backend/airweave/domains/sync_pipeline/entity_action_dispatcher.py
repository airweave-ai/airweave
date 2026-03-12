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
    from airweave.platform.contexts.runtime import SyncRuntime


class EntityActionDispatcher:
    """Dispatches entity actions to all registered handlers concurrently.

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

    def __init__(self, handlers: List[EntityActionHandler]):
        """Initialize with handler list, separating Postgres from destinations."""
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
        runtime: "SyncRuntime",
    ) -> None:
        """Dispatch action batch to all handlers.

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

        await self._dispatch_to_destinations(batch, sync_context, runtime)

        if self._postgres_handler:
            await self._dispatch_to_postgres(batch, sync_context, runtime)

        sync_context.logger.debug("[EntityDispatcher] All handlers completed successfully")

    async def dispatch_orphan_cleanup(
        self,
        orphan_entity_ids: List[str],
        sync_context: "SyncContext",
    ) -> None:
        """Dispatch orphan cleanup to ALL handlers concurrently.

        Raises:
            SyncFailureError: If any handler fails cleanup
        """
        if not orphan_entity_ids:
            return

        all_handlers = list(self._destination_handlers)
        if self._postgres_handler:
            all_handlers.append(self._postgres_handler)

        if not all_handlers:
            return

        sync_context.logger.info(
            f"[EntityDispatcher] Dispatching orphan cleanup for {len(orphan_entity_ids)} entities "
            f"to {len(all_handlers)} handlers"
        )

        tasks = [
            asyncio.create_task(
                self._dispatch_orphan_to_handler(handler, orphan_entity_ids, sync_context),
                name=f"orphan-{handler.name}",
            )
            for handler in all_handlers
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

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

    async def _dispatch_to_destinations(
        self,
        batch: EntityActionBatch,
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> None:
        """Dispatch to all destination handlers concurrently.

        Raises:
            SyncFailureError: If any destination handler fails
        """
        if not self._destination_handlers:
            return

        tasks = [
            asyncio.create_task(
                self._dispatch_to_handler(handler, batch, sync_context, runtime),
                name=f"handler-{handler.name}",
            )
            for handler in self._destination_handlers
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

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
        runtime: "SyncRuntime",
    ) -> None:
        """Dispatch to PostgreSQL metadata handler (after destinations succeed).

        Raises:
            SyncFailureError: If postgres handler fails
        """
        try:
            await self._postgres_handler.handle_batch(batch, sync_context, runtime)
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
        runtime: "SyncRuntime",
    ) -> None:
        """Dispatch to single handler with error wrapping.

        Raises:
            SyncFailureError: If handler fails
        """
        try:
            await handler.handle_batch(batch, sync_context, runtime)
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
