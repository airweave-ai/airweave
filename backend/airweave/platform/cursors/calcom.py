"""Cal.com incremental sync cursor (last_updated_at watermark)."""

from typing import Optional

from pydantic import Field

from ._base import BaseCursor


class CalComCursor(BaseCursor):
    """Cal.com incremental sync cursor using booking updatedAt watermark.

    Tracks the ISO8601 timestamp of the last seen booking.updatedAt so that
    subsequent syncs can request only bookings changed after this point via
    the `afterUpdatedAt` query parameter.
    """

    last_updated_at: Optional[str] = Field(
        default=None,
        description=(
            "ISO8601 timestamp of the most recently processed booking.updatedAt "
            "value (UTC). Used with the `afterUpdatedAt` filter."
        ),
    )
