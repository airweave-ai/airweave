"""Action resolver for access control memberships.

Supports two modes:
1. Full sync: MembershipTuple list → ACUpsertAction (with orphan detection in pipeline)
2. Incremental sync: MembershipChange list → ACUpsertAction/ACDeleteAction/etc.
"""

from typing import TYPE_CHECKING, List

from airweave.platform.access_control.schemas import (
    ACLChangeType,
    MembershipChange,
    MembershipTuple,
)
from airweave.platform.sync.actions.access_control.types import (
    ACActionBatch,
    ACDeleteAction,
    ACDeleteGroupAction,
    ACDeleteMemberAction,
    ACUpsertAction,
)

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext


class ACActionResolver:
    """Resolves membership data to action objects.

    Supports two input types:
    - MembershipTuple (full sync): All become ACUpsertAction, orphan detection done separately
    - MembershipChange (incremental sync): Mapped to specific action types based on change_type

    The resolver is stateless - it converts input to actions. The pipeline handles
    tracking, orphan detection, and cursor management.
    """

    async def resolve(
        self,
        memberships: List[MembershipTuple],
        sync_context: "SyncContext",
    ) -> ACActionBatch:
        """Resolve membership tuples to actions (full sync mode).

        Args:
            memberships: Membership tuples to resolve
            sync_context: Sync context with logger

        Returns:
            ACActionBatch with resolved actions
        """
        if not memberships:
            return ACActionBatch()

        # Deduplicate within batch
        unique = self._deduplicate(memberships)

        # Full sync: all memberships are upserts
        # Orphan detection handled separately in the pipeline
        upserts = [ACUpsertAction(membership=m) for m in unique]

        batch = ACActionBatch(upserts=upserts)

        sync_context.logger.debug(f"[ACResolver] Resolved full sync: {batch.summary()}")

        return batch

    async def resolve_changes(
        self,
        changes: List[MembershipChange],
        sync_context: "SyncContext",
    ) -> ACActionBatch:
        """Resolve membership changes to actions (incremental sync mode).

        Maps change types to action types:
        - ADD → ACUpsertAction (creates MembershipTuple)
        - REMOVE → ACDeleteAction (creates MembershipTuple for key)
        - DELETE_USER → ACDeleteMemberAction (bulk delete by member)
        - DELETE_GROUP → ACDeleteGroupAction (bulk delete by group)

        Args:
            changes: List of membership changes from DirSync
            sync_context: Sync context with logger

        Returns:
            ACActionBatch with resolved actions
        """
        if not changes:
            return ACActionBatch()

        upserts: List[ACUpsertAction] = []
        deletes: List[ACDeleteAction] = []
        delete_members: List[ACDeleteMemberAction] = []
        delete_groups: List[ACDeleteGroupAction] = []

        for change in changes:
            if change.change_type == ACLChangeType.ADD:
                # ADD → upsert the membership
                if change.group_id:
                    membership = MembershipTuple(
                        member_id=change.member_id,
                        member_type=change.member_type,
                        group_id=change.group_id,
                        group_name=change.group_name,
                    )
                    upserts.append(ACUpsertAction(membership=membership))

            elif change.change_type == ACLChangeType.REMOVE:
                # REMOVE → delete specific membership
                if change.group_id:
                    membership = MembershipTuple(
                        member_id=change.member_id,
                        member_type=change.member_type,
                        group_id=change.group_id,
                        group_name=change.group_name,
                    )
                    deletes.append(ACDeleteAction(membership=membership))

            elif change.change_type == ACLChangeType.DELETE_USER:
                # DELETE_USER → delete all memberships for this user
                delete_members.append(
                    ACDeleteMemberAction(
                        member_id=change.member_id,
                        member_type="user",
                    )
                )

            elif change.change_type == ACLChangeType.DELETE_GROUP:
                # DELETE_GROUP → delete all memberships where this is the parent group
                # Note: For DELETE_GROUP, member_id contains the group_id
                delete_groups.append(ACDeleteGroupAction(group_id=change.member_id))

        batch = ACActionBatch(
            upserts=upserts,
            deletes=deletes,
            delete_members=delete_members,
            delete_groups=delete_groups,
        )

        sync_context.logger.debug(f"[ACResolver] Resolved incremental: {batch.summary()}")

        return batch

    def _deduplicate(self, memberships: List[MembershipTuple]) -> List[MembershipTuple]:
        """Deduplicate by (member_id, member_type, group_id)."""
        seen = set()
        unique = []
        for m in memberships:
            key = (m.member_id, m.member_type, m.group_id)
            if key not in seen:
                seen.add(key)
                unique.append(m)
        return unique
