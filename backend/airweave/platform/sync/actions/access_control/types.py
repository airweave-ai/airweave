"""Access control action types for membership sync pipeline.

Simpler than entity types - memberships are identified by
(member_id, member_type, group_id) tuples.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from airweave.platform.access_control.schemas import MembershipTuple


# =============================================================================
# AC Action Types
# =============================================================================


@dataclass
class ACInsertAction:
    """Membership should be inserted (new membership, not in database)."""

    membership: "MembershipTuple"

    @property
    def member_id(self) -> str:
        """Get the member ID."""
        return self.membership.member_id

    @property
    def group_id(self) -> str:
        """Get the group ID."""
        return self.membership.group_id


@dataclass
class ACUpdateAction:
    """Membership should be updated (metadata changed from stored value)."""

    membership: "MembershipTuple"

    @property
    def member_id(self) -> str:
        """Get the member ID."""
        return self.membership.member_id

    @property
    def group_id(self) -> str:
        """Get the group ID."""
        return self.membership.group_id


@dataclass
class ACDeleteAction:
    """Membership should be deleted (stale membership to remove)."""

    membership: "MembershipTuple"

    @property
    def member_id(self) -> str:
        """Get the member ID."""
        return self.membership.member_id

    @property
    def group_id(self) -> str:
        """Get the group ID."""
        return self.membership.group_id


@dataclass
class ACKeepAction:
    """Membership is unchanged (hash matches stored value)."""

    membership: "MembershipTuple"

    @property
    def member_id(self) -> str:
        """Get the member ID."""
        return self.membership.member_id

    @property
    def group_id(self) -> str:
        """Get the group ID."""
        return self.membership.group_id


@dataclass
class ACUpsertAction:
    """Membership should be upserted (insert or update on conflict).

    Currently ALL memberships use this action type (no hash comparison).
    This is the default action until we implement more sophisticated
    change detection.
    """

    membership: "MembershipTuple"

    @property
    def member_id(self) -> str:
        """Get the member ID."""
        return self.membership.member_id

    @property
    def group_id(self) -> str:
        """Get the group ID."""
        return self.membership.group_id


# =============================================================================
# AC Action Batch
# =============================================================================


@dataclass
class ACActionBatch:
    """Container for a batch of resolved access control membership actions."""

    inserts: List[ACInsertAction] = field(default_factory=list)
    updates: List[ACUpdateAction] = field(default_factory=list)
    deletes: List[ACDeleteAction] = field(default_factory=list)
    keeps: List[ACKeepAction] = field(default_factory=list)
    upserts: List[ACUpsertAction] = field(default_factory=list)

    @property
    def has_mutations(self) -> bool:
        """Check if batch has any mutation actions."""
        return bool(self.inserts or self.updates or self.deletes or self.upserts)

    @property
    def mutation_count(self) -> int:
        """Get total count of mutation actions."""
        return len(self.inserts) + len(self.updates) + len(self.deletes) + len(self.upserts)

    @property
    def total_count(self) -> int:
        """Get total count of all actions including KEEP."""
        return self.mutation_count + len(self.keeps)

    def summary(self) -> str:
        """Get a summary string of the batch."""
        parts = []
        if self.inserts:
            parts.append(f"{len(self.inserts)} inserts")
        if self.updates:
            parts.append(f"{len(self.updates)} updates")
        if self.deletes:
            parts.append(f"{len(self.deletes)} deletes")
        if self.upserts:
            parts.append(f"{len(self.upserts)} upserts")
        if self.keeps:
            parts.append(f"{len(self.keeps)} keeps")
        return ", ".join(parts) if parts else "empty"

    def get_memberships(self) -> List["MembershipTuple"]:
        """Get all membership tuples for processing (from upserts)."""
        return [action.membership for action in self.upserts]
