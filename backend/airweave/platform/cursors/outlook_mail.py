"""Outlook Mail cursor schema for incremental sync."""

from typing import Dict, Optional

from pydantic import Field

from ._base import BaseCursor


class OutlookMailCursor(BaseCursor):
    """Outlook Mail delta API cursor with per-folder tracking.

    Outlook Mail uses Microsoft Graph's delta API to track changes to mail folders.
    Each folder maintains its own delta link URL that can be used to fetch only
    changes since the last sync.

    The cursor maintains both a primary delta link (for backward compatibility)
    and per-folder delta links for parallel processing.

    Reference: https://learn.microsoft.com/en-us/graph/delta-query-messages
    """

    delta_link: Optional[str] = Field(
        default=None, description="Primary delta link URL (legacy, for last folder synced)"
    )
    folder_id: Optional[str] = Field(default=None, description="Last synced folder ID (legacy)")
    folder_name: Optional[str] = Field(default=None, description="Last synced folder name (legacy)")
    last_sync: Optional[str] = Field(
        default=None, description="ISO 8601 timestamp of last sync (legacy)"
    )
    folder_delta_links: Dict[str, str] = Field(
        default_factory=dict,
        description="Per-folder delta link URLs as folder_id -> delta_link mapping",
    )
    folder_names: Dict[str, str] = Field(
        default_factory=dict, description="Folder ID to name mapping for reference"
    )
    folder_last_sync: Dict[str, str] = Field(
        default_factory=dict,
        description="Per-folder last sync timestamps as folder_id -> ISO 8601 timestamp",
    )




