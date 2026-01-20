"""PostgreSQL handler for access control memberships.

Implements ACActionHandler protocol for membership persistence.
Written with separate methods per action type for extensibility.

Supports:
- Upserts: Insert or update on conflict (full sync)
- Deletes: Delete specific membership by key (incremental sync)
- Delete by member: Delete all memberships for a user/group (AD deletion)
- Delete by group: Delete all memberships where group is parent (AD deletion)
"""

from typing import TYPE_CHECKING, List

from airweave import crud
from airweave.db.session import get_db_context
from airweave.platform.sync.actions.access_control import (
    ACActionBatch,
    ACDeleteAction,
    ACDeleteGroupAction,
    ACDeleteMemberAction,
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

    Implements ACActionHandler protocol. Supports all action types:
    - Upserts: Bulk insert/update for full sync
    - Deletes: Specific membership removal for incremental sync
    - Delete by member/group: Bulk removal when AD entities are deleted
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
            # Handle upserts (full sync default)
            if batch.upserts:
                count = await self.handle_upserts(batch.upserts, sync_context)
                total_count += count

            # Handle specific deletes (incremental: user removed from group)
            if batch.deletes:
                count = await self.handle_deletes(batch.deletes, sync_context)
                total_count += count

            # Handle bulk delete by member (incremental: user/group deleted from AD)
            if batch.delete_members:
                count = await self.handle_delete_members(batch.delete_members, sync_context)
                total_count += count

            # Handle bulk delete by group (incremental: group deleted from AD)
            if batch.delete_groups:
                count = await self.handle_delete_groups(batch.delete_groups, sync_context)
                total_count += count

            # Future: Handle individual action types when we add hash comparison
            if batch.inserts:
                count = await self.handle_inserts(batch.inserts, sync_context)
                total_count += count
            if batch.updates:
                count = await self.handle_updates(batch.updates, sync_context)
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

        Uses batched upserts to avoid massive transactions that can crash
        PostgreSQL or the Python driver when processing 100K+ memberships.

        Args:
            actions: List of upsert actions
            sync_context: Sync context

        Returns:
            Number of memberships upserted
        """
        if not actions:
            return 0

        memberships = [action.membership for action in actions]

        # Batch upserts to prevent massive transactions
        # PostgreSQL limit is 32,767 parameters. Each membership has ~10 columns.
        # 3000 * 10 = 30,000 params (safely under the limit)
        BATCH_SIZE = 2000
        total_count = 0

        for i in range(0, len(memberships), BATCH_SIZE):
            batch = memberships[i : i + BATCH_SIZE]

            async with get_db_context() as db:
                count = await crud.access_control_membership.bulk_create(
                    db=db,
                    memberships=batch,
                    organization_id=sync_context.organization_id,
                    source_connection_id=sync_context.source_connection_id,
                    source_name=sync_context.connection.short_name,
                )

            total_count += count

            # Log progress for large batches
            if len(memberships) > BATCH_SIZE:
                sync_context.logger.info(
                    f"[ACPostgresHandler] Batch upsert progress: "
                    f"{min(i + BATCH_SIZE, len(memberships))}/{len(memberships)} memberships"
                )

        sync_context.logger.debug(f"[ACPostgresHandler] Upserted {total_count} memberships total")

        return total_count

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
        """Handle delete actions - remove specific memberships by key.

        Used in incremental sync when a user is removed from a specific group.
        Each action targets one membership identified by (member_id, member_type, group_id).

        Args:
            actions: List of delete actions
            sync_context: Sync context

        Returns:
            Number of memberships deleted
        """
        if not actions:
            return 0

        deleted_count = 0

        async with get_db_context() as db:
            for action in actions:
                deleted = await crud.access_control_membership.delete_by_key(
                    db=db,
                    member_id=action.membership.member_id,
                    member_type=action.membership.member_type,
                    group_id=action.membership.group_id,
                    source_connection_id=sync_context.source_connection_id,
                )
                if deleted:
                    deleted_count += 1
                    sync_context.logger.debug(
                        f"[ACPostgresHandler] Deleted membership: "
                        f"{action.member_id} → {action.group_id}"
                    )

        if deleted_count > 0:
            sync_context.logger.info(f"[ACPostgresHandler] Deleted {deleted_count} memberships")

        return deleted_count

    async def handle_delete_members(
        self,
        actions: List[ACDeleteMemberAction],
        sync_context: "SyncContext",
    ) -> int:
        """Handle delete-by-member actions - remove all memberships for a user/group.

        Used in incremental sync when a user or group is deleted from AD.
        Removes ALL memberships where this entity is the member.

        Args:
            actions: List of delete member actions
            sync_context: Sync context

        Returns:
            Number of memberships deleted
        """
        if not actions:
            return 0

        deleted_count = 0

        async with get_db_context() as db:
            for action in actions:
                count = await crud.access_control_membership.delete_by_member(
                    db=db,
                    member_id=action.member_id,
                    member_type=action.member_type,
                    source_connection_id=sync_context.source_connection_id,
                )
                deleted_count += count
                if count > 0:
                    sync_context.logger.info(
                        f"[ACPostgresHandler] Deleted {action.member_type} {action.member_id}: "
                        f"removed {count} memberships"
                    )

        return deleted_count

    async def handle_delete_groups(
        self,
        actions: List[ACDeleteGroupAction],
        sync_context: "SyncContext",
    ) -> int:
        """Handle delete-by-group actions - remove all memberships for a group.

        Used in incremental sync when a group is deleted from AD.
        Removes ALL memberships where this group is the parent group.

        Args:
            actions: List of delete group actions
            sync_context: Sync context

        Returns:
            Number of memberships deleted
        """
        if not actions:
            return 0

        deleted_count = 0

        async with get_db_context() as db:
            for action in actions:
                count = await crud.access_control_membership.delete_by_group(
                    db=db,
                    group_id=action.group_id,
                    source_connection_id=sync_context.source_connection_id,
                )
                deleted_count += count
                if count > 0:
                    sync_context.logger.info(
                        f"[ACPostgresHandler] Deleted group {action.group_id}: "
                        f"removed {count} memberships"
                    )

        return deleted_count
