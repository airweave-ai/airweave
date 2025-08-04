"""Sync cursor module for tracking sync progress."""

from uuid import UUID


class SyncCursor:
    """Cursor for a sync.

    This class is used to track the progress of a sync.
    """

    def __init__(self, sync_id: UUID, cursor_data: dict | None = None):
        """Initialize a sync cursor with the given sync ID."""
        self.sync_id = sync_id
        self.cursor_data = cursor_data or {}
