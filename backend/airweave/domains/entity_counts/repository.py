"""Entity count repository -- wraps crud.entity_count.

Only includes methods the source connections domain currently needs.
"""

from typing import Any, List
from uuid import UUID

from airweave import crud


class EntityCountRepository:
    """Repository wrapping crud.entity_count."""

    async def get_counts_per_sync_and_type(self, db: Any, sync_id: UUID) -> List[Any]:
        """Get entity counts grouped by type for a sync."""
        return await crud.entity_count.get_counts_per_sync_and_type(db, sync_id)
