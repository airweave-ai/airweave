"""PostgreSQL handler for access control memberships.

Implements ACActionHandler protocol for membership persistence.
Written with separate methods per action type for future extensibility.
"""

from typing import TYPE_CHECKING, List

from airweave import crud
from airweave.db.session import get_db_context
from airweave.platform.sync.actions.access_control import (
    ACActionBatch,
    ACDeleteAction,
    ACInsertAction,
    ACUpdateAction,
    ACUpsertAction,
)
from airweave.platform.sync.exceptions import SyncFailureError
from airweave.platform.sync.handlers.protocol import ACActionHandler

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext


class ACPostgresHandler(ACActionHandler):
    """Persists access control memberships to PostgreSQL.

    Implements ACActionHandler protocol. Structured with separate methods
    per action type for easy extensibility when we add delete/update actions.
    """

    @property
    def name(self) -> str:
        """Handler name for logging and debugging."""
        return "access_control_postgres"

    async def handle_batch(
        self,
        batch: ACActionBatch,
        sync_context: "SyncContext",
    ) -> int:
        """Handle an access control membership action batch.

        Dispatches to specific handlers for each action type.

        Args:
            batch: ACActionBatch with resolved actions
            sync_context: Sync context

        Returns:
            Number of memberships processed

        Raises:
            SyncFailureError: If any operation fails
        """
        if not batch.has_mutations:
            return 0

        total_count = 0

        try:
            # Handle upserts (current default)
            if batch.upserts:
                count = await self.handle_upserts(batch.upserts, sync_context)
                total_count += count

            # Future: Handle individual action types when we add hash comparison
            if batch.inserts:
                count = await self.handle_inserts(batch.inserts, sync_context)
                total_count += count
            if batch.updates:
                count = await self.handle_updates(batch.updates, sync_context)
                total_count += count
            if batch.deletes:
                count = await self.handle_deletes(batch.deletes, sync_context)
                total_count += count

            return total_count

        except SyncFailureError:
            raise
        except Exception as e:
            sync_context.logger.error(
                f"[ACPostgresHandler] Failed: {e}",
                exc_info=True,
            )
            raise SyncFailureError(f"Access control membership persistence failed: {e}")

    async def handle_upserts(
        self,
        actions: List[ACUpsertAction],
        sync_context: "SyncContext",
    ) -> int:
        """Handle upsert actions - bulk insert with ON CONFLICT.

        Args:
            actions: List of upsert actions
            sync_context: Sync context

        Returns:
            Number of memberships upserted
        """
        if not actions:
            return 0

        memberships = [action.membership for action in actions]

        async with get_db_context() as db:
            count = await crud.access_control_membership.bulk_create(
                db=db,
                memberships=memberships,
                organization_id=sync_context.scope.organization_id,
                source_connection_id=sync_context.source.source_connection_id,
                source_name=sync_context.source.source_connection.short_name,
            )

        sync_context.logger.debug(f"[ACPostgresHandler] Upserted {count} memberships")

        return count

    async def handle_inserts(
        self,
        actions: List[ACInsertAction],
        sync_context: "SyncContext",
    ) -> int:
        """Handle insert actions.

        Future: Implement when we add hash comparison for new memberships.
        Currently no-op as all memberships use upsert.
        """
        return 0

    async def handle_updates(
        self,
        actions: List[ACUpdateAction],
        sync_context: "SyncContext",
    ) -> int:
        """Handle update actions.

        Future: Implement when we add hash comparison for changed memberships.
        Currently no-op as all memberships use upsert.
        """
        return 0

    async def handle_deletes(
        self,
        actions: List[ACDeleteAction],
        sync_context: "SyncContext",
    ) -> int:
        """Handle delete actions.

        Future: Implement when we add stale membership cleanup.
        Currently no-op.
        """
        return 0
