"""Action dispatcher for access control memberships.

Routes membership actions to registered handlers.
Currently only PostgresHandler, but architecture supports Redis, etc.
"""

from typing import TYPE_CHECKING, List

from airweave.platform.sync.actions.access_control.types import ACActionBatch
from airweave.platform.sync.exceptions import SyncFailureError

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext
    from airweave.platform.sync.handlers.protocol import ACActionHandler


class ACActionDispatcher:
    """Dispatches access control membership actions to handlers.

    Currently single-handler (Postgres), but architecture supports
    future multi-handler use (Redis cache, etc.).
    """

    def __init__(self, handlers: List["ACActionHandler"]):
        """Initialize dispatcher with handlers.

        Args:
            handlers: List of access control membership handlers
        """
        self._handlers = handlers

    async def dispatch(
        self,
        batch: ACActionBatch,
        sync_context: "SyncContext",
    ) -> int:
        """Dispatch action batch to all handlers.

        Args:
            batch: Resolved membership action batch
            sync_context: Sync context

        Returns:
            Total number of memberships processed

        Raises:
            SyncFailureError: If any handler fails
        """
        if not batch.has_mutations:
            sync_context.logger.debug("[ACDispatcher] No mutations to dispatch")
            return 0

        sync_context.logger.debug(
            f"[ACDispatcher] Dispatching {batch.summary()} to {len(self._handlers)} handler(s)"
        )

        total_count = 0

        # Currently sequential (only 1 handler)
        # Future: could use asyncio.gather for concurrent handlers
        for handler in self._handlers:
            try:
                count = await handler.handle_batch(batch, sync_context)
                total_count += count
            except SyncFailureError:
                raise
            except Exception as e:
                sync_context.logger.error(
                    f"[ACDispatcher] Handler {handler.name} failed: {e}",
                    exc_info=True,
                )
                raise SyncFailureError(f"Handler {handler.name} failed: {e}")

        sync_context.logger.debug(f"[ACDispatcher] All handlers completed, {total_count} processed")

        return total_count
