"""SharePoint Online cursor schema for incremental sync.

SPO supports incremental change tracking via:
1. Graph delta queries for drive items (/drives/{id}/root/delta)
2. Group membership polling for ACL changes (no DirSync equivalent)
"""

from datetime import datetime
from typing import Dict

from pydantic import Field

from ._base import BaseCursor


class SharePointOnlineCursor(BaseCursor):
    """SharePoint Online incremental sync cursor.

    Tracks two independent change streams:
    1. Entity sync via Graph delta queries (per-drive delta tokens)
    2. ACL sync via group membership snapshots
    """

    drive_delta_tokens: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of drive_id -> delta token from Graph delta query.",
    )

    last_entity_sync_timestamp: str = Field(
        default="",
        description="ISO 8601 timestamp of last successful entity sync.",
    )

    last_entity_changes_count: int = Field(
        default=0,
        description="Number of entity changes processed in last incremental sync.",
    )

    last_acl_sync_timestamp: str = Field(
        default="",
        description="ISO 8601 timestamp of last successful ACL sync.",
    )

    last_acl_changes_count: int = Field(
        default=0,
        description="Number of ACL changes processed in last incremental sync.",
    )

    full_sync_required: bool = Field(
        default=True,
        description="Whether a full sync is required.",
    )

    last_full_sync_timestamp: str = Field(
        default="",
        description="ISO 8601 timestamp of last full sync.",
    )

    total_entities_synced: int = Field(
        default=0,
        description="Total entities synced in last full sync.",
    )

    total_acl_memberships: int = Field(
        default=0,
        description="Total ACL memberships generated in last sync.",
    )

    synced_site_ids: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of site_id -> site display name (discovered sites).",
    )

    synced_drive_ids: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of drive_id -> drive name (discovered drives).",
    )

    def has_delta_tokens(self) -> bool:
        """Return whether any delta tokens have been stored."""
        return bool(self.drive_delta_tokens)

    def needs_full_sync(self) -> bool:
        """Return whether a full sync is needed (flag set or no delta tokens)."""
        if self.full_sync_required:
            return True
        if not self.drive_delta_tokens:
            return True
        return False

    def needs_periodic_full_sync(self, interval_days: int = 7) -> bool:
        """Return whether enough time has elapsed to warrant a periodic full sync."""
        if not self.last_full_sync_timestamp:
            return True
        try:
            last_full = datetime.fromisoformat(self.last_full_sync_timestamp)
            elapsed = datetime.utcnow() - last_full
            return elapsed.days >= interval_days
        except (ValueError, TypeError):
            return True

    def update_entity_cursor(
        self,
        drive_id: str,
        delta_token: str,
        changes_count: int,
        is_full_sync: bool = False,
    ) -> None:
        """Update entity sync state for a given drive."""
        self.drive_delta_tokens[drive_id] = delta_token
        self.last_entity_sync_timestamp = datetime.utcnow().isoformat()
        self.last_entity_changes_count = changes_count
        if is_full_sync:
            self.last_full_sync_timestamp = datetime.utcnow().isoformat()
            self.total_entities_synced = changes_count
            self.full_sync_required = False

    def update_acl_cursor(self, changes_count: int) -> None:
        """Update ACL sync state."""
        self.last_acl_sync_timestamp = datetime.utcnow().isoformat()
        self.last_acl_changes_count = changes_count

    def mark_full_sync_required(self, reason: str = "") -> None:
        """Flag that a full sync is needed on the next run."""
        self.full_sync_required = True
