"""Zoom cursor schema for incremental sync.

Tracks the last successful sync timestamp so subsequent syncs can
filter out already-processed meetings and recordings.
"""

from pydantic import Field

from ._base import BaseCursor


class ZoomCursor(BaseCursor):
    """Zoom incremental sync cursor using timestamps.

    We store the sync start time as an ISO 8601 string so that the
    next run can filter entities whose effective timestamps are
    greater than this value.
    """

    last_synced_at: str = Field(
        default="",
        description="ISO 8601 timestamp of the last successful Zoom sync start time",
    )
