"""Tracker for ACL memberships encountered during sync.

ACLMembershipTracker is used for:
- Deduplication within a single sync run
- Orphan detection (memberships in DB but not seen = revoked permissions)

This is critical for security: when permissions are revoked at the source,
we need to detect and delete the corresponding membership records.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Set, Tuple
from uuid import UUID

if TYPE_CHECKING:
    from airweave.core.logging import ContextualLogger


@dataclass
class ACLSyncStats:
    """Statistics for ACL membership sync."""

    encountered: int = 0
    duplicates_skipped: int = 0
    upserted: int = 0
    deleted: int = 0


class ACLMembershipTracker:
    """Tracks all ACL memberships encountered during sync.

    Used for:
    - Deduplication within a sync (same membership yielded multiple times)
    - Orphan detection (memberships in DB but not seen during sync = revoked)

    The unique key for a membership is: (member_id, member_type, group_id)
    This matches the unique constraint on the access_control_membership table
    (scoped by organization_id and source_connection_id).

    Thread-safety: This tracker is designed to be used within a single sync
    context and does not need async locks since membership collection happens
    sequentially in the orchestrator.
    """

    def __init__(
        self,
        source_connection_id: UUID,
        organization_id: UUID,
        logger: "ContextualLogger",
    ):
        """Initialize the ACL membership tracker.

        Args:
            source_connection_id: The source connection ID (scopes the memberships)
            organization_id: Organization ID for multi-tenant isolation
            logger: Contextual logger for debugging
        """
        self.source_connection_id = source_connection_id
        self.organization_id = organization_id
        self.logger = logger

        # Key: (member_id, member_type, group_id) - matches unique constraint
        self._encountered: Set[Tuple[str, str, str]] = set()

        # Stats tracking
        self.stats = ACLSyncStats()

    def track_membership(
        self,
        member_id: str,
        member_type: str,
        group_id: str,
    ) -> bool:
        """Track a membership as encountered. Returns True if new, False if duplicate.

        Args:
            member_id: Member identifier (email for users, ID for groups)
            member_type: "user" or "group"
            group_id: The group being joined

        Returns:
            True if this is a new membership (first time encountered in this sync)
            False if this is a duplicate (already encountered in this sync)
        """
        key = (member_id, member_type, group_id)
        if key in self._encountered:
            self.stats.duplicates_skipped += 1
            return False

        self._encountered.add(key)
        self.stats.encountered += 1
        return True

    def get_encountered_keys(self) -> Set[Tuple[str, str, str]]:
        """Get all encountered membership keys for orphan detection.

        Returns a copy to prevent external modification.

        Returns:
            Set of (member_id, member_type, group_id) tuples
        """
        return self._encountered.copy()

    def get_encountered_count(self) -> int:
        """Get count of unique memberships encountered."""
        return len(self._encountered)

    def record_upserted(self, count: int) -> None:
        """Record number of memberships upserted to database."""
        self.stats.upserted = count

    def record_deleted(self, count: int) -> None:
        """Record number of orphan memberships deleted."""
        self.stats.deleted = count

    def get_stats(self) -> ACLSyncStats:
        """Get sync statistics."""
        return self.stats

    def log_summary(self) -> None:
        """Log a summary of the ACL sync operation."""
        self.logger.info(
            f"🔐 ACL Sync Summary: "
            f"encountered={self.stats.encountered}, "
            f"duplicates_skipped={self.stats.duplicates_skipped}, "
            f"upserted={self.stats.upserted}, "
            f"deleted={self.stats.deleted}"
        )
