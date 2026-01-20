"""Access control action types for membership sync pipeline.

Simpler than entity types - memberships are identified by
(member_id, member_type, group_id) tuples.

Supports two input types:
- MembershipTuple: Full sync (state-based, requires orphan detection)
- MembershipChange: Incremental sync (event-based, explicit adds/removes)
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
    """Membership should be deleted (specific membership to remove).

    Used when a user is removed from a specific group.
    Key: (member_id, member_type, group_id)
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


@dataclass
class ACDeleteMemberAction:
    """Delete ALL memberships for a member (user/group deleted from AD).

    Used when a user or group is deleted from Active Directory.
    Removes all memberships where this entity is the member.
    """

    member_id: str
    member_type: str  # "user" or "group"


@dataclass
class ACDeleteGroupAction:
    """Delete ALL memberships where group_id matches (group deleted from AD).

    Used when a group is deleted from Active Directory.
    Removes all memberships where this group is the parent group.
    """

    group_id: str


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

    # Bulk delete actions (for incremental sync when AD entities are deleted)
    delete_members: List[ACDeleteMemberAction] = field(default_factory=list)
    delete_groups: List[ACDeleteGroupAction] = field(default_factory=list)

    @property
    def has_mutations(self) -> bool:
        """Check if batch has any mutation actions."""
        return bool(
            self.inserts
            or self.updates
            or self.deletes
            or self.upserts
            or self.delete_members
            or self.delete_groups
        )

    @property
    def mutation_count(self) -> int:
        """Get total count of mutation actions."""
        return (
            len(self.inserts)
            + len(self.updates)
            + len(self.deletes)
            + len(self.upserts)
            + len(self.delete_members)
            + len(self.delete_groups)
        )

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
        if self.delete_members:
            parts.append(f"{len(self.delete_members)} delete_members")
        if self.delete_groups:
            parts.append(f"{len(self.delete_groups)} delete_groups")
        return ", ".join(parts) if parts else "empty"

    def get_memberships(self) -> List["MembershipTuple"]:
        """Get all membership tuples for processing (from upserts)."""
        return [action.membership for action in self.upserts]
