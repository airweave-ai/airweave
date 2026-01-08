"""Action resolver for access control memberships.

Currently simple: all memberships become ACUpsertAction.
Future: May compare hashes to determine INSERT/UPDATE/KEEP/DELETE.
"""

from typing import TYPE_CHECKING, List

from airweave.platform.access_control.schemas import MembershipTuple
from airweave.platform.sync.actions.access_control.types import (
    ACActionBatch,
    ACUpsertAction,
)

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext


class ACActionResolver:
    """Resolves membership tuples to action objects.

    Currently all memberships become ACUpsertAction (no DB comparison).
    This is intentional - the handler uses ON CONFLICT for efficiency.

    Future enhancements:
    - Hash comparison to detect unchanged memberships (KEEP action)
    - Orphan detection for stale memberships (DELETE action)
    """

    async def resolve(
        self,
        memberships: List[MembershipTuple],
        sync_context: "SyncContext",
    ) -> ACActionBatch:
        """Resolve memberships to actions.

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

        # Currently: all memberships are upserts
        # Future: could compare against DB to determine INSERT/UPDATE/KEEP
        upserts = [ACUpsertAction(membership=m) for m in unique]

        batch = ACActionBatch(upserts=upserts)

        sync_context.logger.debug(f"[ACResolver] Resolved: {batch.summary()}")

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
