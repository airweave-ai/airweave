"""Linear incremental sync cursor using updatedAt timestamps."""

from pydantic import Field

from ._base import BaseCursor


class LinearCursor(BaseCursor):
    """Linear incremental sync cursor using updatedAt timestamps.

    Linear tracks entity modifications via the updatedAt field on all
    resource types (issues, projects, teams, users). We capture the sync
    start time so the next run can filter to only changed entities.
    """

    last_synced_at: str = Field(
        default="",
        description="ISO 8601 timestamp of the last successful sync start time",
    )
