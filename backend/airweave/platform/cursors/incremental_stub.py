"""Incremental stub cursor schema for testing continuous sync."""

from pydantic import Field

from ._base import BaseCursor


class IncrementalStubCursor(BaseCursor):
    """Cursor for the incremental stub source.

    Tracks the last entity index that was synced, so subsequent syncs
    only generate entities beyond that index.
    """

    last_entity_index: int = Field(
        default=-1,
        description="Index of the last entity synced (-1 means no previous sync)",
    )
    entity_count: int = Field(
        default=0,
        description="Total number of entities at time of last sync",
    )
