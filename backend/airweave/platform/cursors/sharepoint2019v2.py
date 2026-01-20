"""SharePoint 2019 V2 cursor schemas for incremental sync.

SharePoint 2019 supports incremental change tracking via the GetChanges API.
This cursor tracks:
1. Entity changes (files, items) using site collection level change tokens
2. ACL changes (group memberships) using AD DirSync cookies

Key architecture decisions:
- Uses site collection level change tokens (/_api/site/getChanges)
- One source_connection = One site_collection = One cursor
- Separate tracking for entities and ACL (different change mechanisms)
"""

from datetime import datetime
from typing import Optional

from pydantic import Field

from ._base import BaseCursor


class SharePoint2019V2Cursor(BaseCursor):
    """SharePoint 2019 incremental sync cursor using Change Tokens.

    Uses site collection level tracking (/_api/site/getChanges) which
    provides ONE change token that covers the entire site collection
    including all subsites, lists, and items.

    One source_connection → One site_collection → One cursor

    Token Format: "1;3;{ListGUID};{Ticks};{ChangeId}"
    Example: "1;3;a1b2c3d4-...;638664757420130000;1288941838"

    IMPORTANT: Change tokens expire after ~60 days (configurable by farm admin).
    If token is too old, a full sync will be triggered automatically.
    """

    # =========================================================================
    # ENTITY SYNC CURSOR (SharePoint GetChanges API)
    # =========================================================================
    # All fields start empty/None on first sync and get populated after sync completes.

    site_collection_change_token: str = Field(
        default="",
        description="Change token from /_api/site/getChanges. Empty string = first sync.",
    )

    last_entity_sync_timestamp: str = Field(
        default="",
        description="ISO 8601 timestamp of last successful entity sync. Empty = never synced.",
    )

    site_collection_url: str = Field(
        default="",
        description="Site collection URL this cursor tracks.",
    )

    last_entity_changes_count: int = Field(
        default=0,
        description="Number of entity changes processed in last incremental sync.",
    )

    # =========================================================================
    # ACL SYNC CURSOR (AD DirSync Control)
    # =========================================================================
    # All fields start empty/None on first sync and get populated after sync completes.

    acl_dirsync_cookie: str = Field(
        default="",
        description="Base64-encoded DirSync cookie for incremental LDAP sync. Empty = first sync.",
    )

    acl_domain_controller: str = Field(
        default="",
        description="DC hostname/IP used for ACL sync (must be consistent).",
    )

    last_acl_sync_timestamp: str = Field(
        default="",
        description="ISO 8601 timestamp of last successful ACL sync. Empty = never synced.",
    )

    last_acl_changes_count: int = Field(
        default=0,
        description="Number of ACL changes processed in last incremental sync.",
    )

    # =========================================================================
    # SYNC METADATA
    # =========================================================================

    full_sync_required: bool = Field(
        default=True,
        description="Whether a full sync is required (first sync or token expired).",
    )

    last_full_sync_timestamp: str = Field(
        default="",
        description="ISO 8601 timestamp of last full sync. Empty = never had full sync.",
    )

    total_entities_synced: int = Field(
        default=0,
        description="Total entities tracked (for monitoring)",
    )

    total_acl_memberships: int = Field(
        default=0,
        description="Total ACL memberships tracked (for monitoring)",
    )

    def is_entity_token_expired(self, max_age_days: int = 55) -> bool:
        """Check if entity change token is too old.

        SharePoint retains change log for ~60 days by default.
        We use 55 days to be safe and trigger full sync before expiry.

        Args:
            max_age_days: Maximum age in days before forcing full sync

        Returns:
            True if token is expired or missing (empty string = first sync)
        """
        if not self.site_collection_change_token:  # Empty string = no token
            return True

        if not self.last_entity_sync_timestamp:  # Empty string = never synced
            return True

        try:
            last_sync = datetime.fromisoformat(
                self.last_entity_sync_timestamp.replace("Z", "+00:00")
            )
            age_days = (datetime.now(last_sync.tzinfo) - last_sync).days
            return age_days > max_age_days
        except (ValueError, TypeError):
            return True

    def is_acl_cookie_expired(self, max_age_days: int = 55) -> bool:
        """Check if ACL DirSync cookie is too old.

        AD tombstones are retained for ~180 days by default,
        but we use 55 days to align with SharePoint token expiry.

        Args:
            max_age_days: Maximum age in days before forcing full sync

        Returns:
            True if cookie is expired or missing (empty string = first sync)
        """
        if not self.acl_dirsync_cookie:  # Empty string = no cookie
            return True

        if not self.last_acl_sync_timestamp:  # Empty string = never synced
            return True

        try:
            last_sync = datetime.fromisoformat(self.last_acl_sync_timestamp.replace("Z", "+00:00"))
            age_days = (datetime.now(last_sync.tzinfo) - last_sync).days
            return age_days > max_age_days
        except (ValueError, TypeError):
            return True

    def needs_periodic_full_sync(self, interval_days: int = 7) -> bool:
        """Check if periodic full sync is needed for orphan cleanup.

        Even with incremental sync, we should do periodic full syncs to:
        - Clean up orphaned entities that might have been missed
        - Verify data integrity
        - Handle edge cases in change tracking

        Args:
            interval_days: Days between full syncs

        Returns:
            True if full sync is needed (empty string = never had full sync)
        """
        if not self.last_full_sync_timestamp:  # Empty string = never had full sync
            return True

        try:
            last_full = datetime.fromisoformat(self.last_full_sync_timestamp.replace("Z", "+00:00"))
            days_since_full = (datetime.now(last_full.tzinfo) - last_full).days
            return days_since_full >= interval_days
        except (ValueError, TypeError):
            return True

    def update_entity_cursor(
        self,
        new_token: str,
        changes_count: int,
        is_full_sync: bool = False,
    ) -> None:
        """Update entity sync cursor after successful sync.

        Args:
            new_token: New change token from GetChanges response
            changes_count: Number of changes processed
            is_full_sync: Whether this was a full sync
        """
        now = datetime.utcnow().isoformat() + "Z"

        self.site_collection_change_token = new_token
        self.last_entity_sync_timestamp = now
        self.last_entity_changes_count = changes_count

        if is_full_sync:
            self.last_full_sync_timestamp = now
            self.full_sync_required = False

    def update_acl_cursor(
        self,
        new_cookie: str,
        changes_count: int,
        domain_controller: Optional[str] = None,
    ) -> None:
        """Update ACL sync cursor after successful sync.

        Args:
            new_cookie: New DirSync cookie (base64 encoded)
            changes_count: Number of ACL changes processed
            domain_controller: DC used for this sync
        """
        now = datetime.utcnow().isoformat() + "Z"

        self.acl_dirsync_cookie = new_cookie
        self.last_acl_sync_timestamp = now
        self.last_acl_changes_count = changes_count

        if domain_controller:
            self.acl_domain_controller = domain_controller

    def mark_full_sync_required(self, reason: str = "") -> None:
        """Mark that a full sync is required.

        Args:
            reason: Optional reason for logging
        """
        self.full_sync_required = True
        # Keep existing tokens - they might still be useful after full sync
