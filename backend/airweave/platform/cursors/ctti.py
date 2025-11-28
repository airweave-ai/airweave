"""CTTI cursor for incremental sync tracking."""

from pydantic import Field

from ._base import BaseCursor


class CTTICursor(BaseCursor):
    """CTTI incremental sync cursor using last processed NCT_ID.

    NCT_IDs are strictly increasing alphanumeric identifiers (e.g., NCT07252596),
    making them ideal for cursor-based pagination.

    Tracks both position (last_nct_id) and total count (total_synced) to enforce
    the configured limit across all syncs.
    """

    last_nct_id: str = Field(default="", description="Last processed NCT_ID for incremental sync")
    total_synced: int = Field(default=0, description="Total records synced across all runs")
