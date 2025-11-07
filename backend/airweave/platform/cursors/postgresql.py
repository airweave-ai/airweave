"""PostgreSQL cursor schema for incremental sync."""

from typing import Dict

from pydantic import Field

from ._base import BaseCursor


class PostgreSQLCursor(BaseCursor):
    """PostgreSQL per-table cursor tracking.

    PostgreSQL connector tracks cursor values independently per table using
    a timestamp or sequence column. The cursor stores the maximum value seen
    for each table to enable incremental fetching.

    The keys in table_cursors are formatted as "schema.table" (e.g., "public.users").
    The values are ISO 8601 timestamps or sequence numbers depending on the cursor field.
    """

    table_cursors: Dict[str, str] = Field(
        default_factory=dict,
        description="Per-table cursor values as 'schema.table' -> cursor value mapping",
    )




