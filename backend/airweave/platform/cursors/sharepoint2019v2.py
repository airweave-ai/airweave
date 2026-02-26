"""SharePoint 2019 V2 cursor schema for incremental sync.

SharePoint 2019 supports incremental change tracking via the GetChanges API.
This cursor tracks:
1. Entity changes (files, items) using site collection level change tokens
2. ACL changes (group memberships) using AD DirSync cookies

Architecture:
- Uses site collection level change tokens (/_api/site/getChanges)
- One source_connection = one site_collection = one cursor
- Separate tracking for entities and ACL (different change mechanisms)
"""

from datetime import datetime
from typing import Optional

from pydantic import Field

from ._base import BaseCursor


class SharePoint2019V2Cursor(BaseCursor):
    """SharePoint 2019 incremental sync cursor.

    Tracks two independent change streams:
    1. Entity sync via SharePoint GetChanges API (change tokens)
    2. ACL sync via AD DirSync control (LDAP cookies)

    Change tokens have format: "1;3;{GUID};{Ticks};{ChangeId}"
    They expire after ~60 days (configurable by SharePoint farm admin).
    When a token expires, a full sync is triggered automatically.
    """

    # -- Entity sync (SharePoint GetChanges API) --

    site_collection_change_token: str = Field(
        default="",
        description="Change token from /_api/site/getChanges. Empty = first sync.",
    )

    last_entity_sync_timestamp: str = Field(
        default="",
        description="ISO 8601 timestamp of last successful entity sync.",
    )

    site_collection_url: str = Field(
        default="",
        description="Site collection URL this cursor tracks.",
    )

    last_entity_changes_count: int = Field(
        default=0,
        description="Number of entity changes processed in last incremental sync.",
    )

    # -- ACL sync (AD DirSync control) --

    acl_dirsync_cookie: str = Field(
        default="",
        description="Base64-encoded DirSync cookie for incremental LDAP sync.",
    )

    acl_domain_controller: str = Field(
        default="",
        description="DC hostname/IP used for ACL sync (must be consistent across runs).",
    )

    last_acl_sync_timestamp: str = Field(
        default="",
        description="ISO 8601 timestamp of last successful ACL sync.",
    )

    last_acl_changes_count: int = Field(
        default=0,
        description="Number of ACL changes processed in last incremental sync.",
    )

    # -- Sync metadata --

    full_sync_required: bool = Field(
        default=True,
        description="Whether a full sync is required (first sync or token expired).",
    )

    last_full_sync_timestamp: str = Field(
        default="",
        description="ISO 8601 timestamp of last full sync.",
    )

    total_entities_synced: int = Field(
        default=0,
        description="Total entities tracked (for monitoring).",
    )

    total_acl_memberships: int = Field(
        default=0,
        description="Total ACL memberships tracked (for monitoring).",
    )

    # -- Helper methods --

    def is_entity_token_expired(self, max_age_days: int = 55) -> bool:
        """Check if the entity change token is too old.

        SharePoint retains its change log for ~60 days by default.
        We use 55 days to trigger a full sync before actual expiry.

        Args:
            max_age_days: Maximum age in days before forcing full sync.

        Returns:
            True if token is expired or missing.
        """
        if not self.site_collection_change_token or not self.last_entity_sync_timestamp:
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
        """Check if the DirSync cookie is too old.

        AD tombstones are retained for ~180 days by default, but we
        use 55 days to align with SharePoint change token expiry.

        Args:
            max_age_days: Maximum age in days before forcing full ACL sync.

        Returns:
            True if cookie is expired or missing.
        """
        if not self.acl_dirsync_cookie or not self.last_acl_sync_timestamp:
            return True

        try:
            last_sync = datetime.fromisoformat(self.last_acl_sync_timestamp.replace("Z", "+00:00"))
            age_days = (datetime.now(last_sync.tzinfo) - last_sync).days
            return age_days > max_age_days
        except (ValueError, TypeError):
            return True

    def needs_periodic_full_sync(self, interval_days: int = 7) -> bool:
        """Check if a periodic full sync is needed for orphan cleanup.

        Even with incremental sync, periodic full syncs ensure:
        - Orphaned entities missed by change tracking are cleaned up
        - Data integrity is verified
        - Edge cases in change tracking are handled

        Args:
            interval_days: Days between full syncs.

        Returns:
            True if a full sync is overdue.
        """
        if not self.last_full_sync_timestamp:
            return True

        try:
            last_full = datetime.fromisoformat(self.last_full_sync_timestamp.replace("Z", "+00:00"))
            days_since = (datetime.now(last_full.tzinfo) - last_full).days
            return days_since >= interval_days
        except (ValueError, TypeError):
            return True

    def update_entity_cursor(
        self,
        new_token: str,
        changes_count: int,
        is_full_sync: bool = False,
    ) -> None:
        """Update entity sync cursor after a successful sync.

        Args:
            new_token: New change token from GetChanges response.
            changes_count: Number of changes processed.
            is_full_sync: Whether this was a full sync.
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
        """Update ACL sync cursor after a successful ACL sync.

        Args:
            new_cookie: New DirSync cookie (base64 encoded).
            changes_count: Number of ACL changes processed.
            domain_controller: DC used for this sync.
        """
        now = datetime.utcnow().isoformat() + "Z"
        self.acl_dirsync_cookie = new_cookie
        self.last_acl_sync_timestamp = now
        self.last_acl_changes_count = changes_count

        if domain_controller:
            self.acl_domain_controller = domain_controller

    def mark_full_sync_required(self, reason: str = "") -> None:
        """Mark that a full sync is required on the next run.

        Args:
            reason: Optional reason string for logging.
        """
        self.full_sync_required = True
