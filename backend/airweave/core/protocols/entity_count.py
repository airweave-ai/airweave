"""Protocol for entity count data access.

Cross-cutting: used by source connections (response builder), admin.
"""

from typing import Any, List, Protocol
from uuid import UUID


class EntityCountRepositoryProtocol(Protocol):
    """Data access for EntityCount records."""

    async def get_counts_per_sync_and_type(self, db: Any, sync_id: UUID) -> List[Any]:
        """Get entity counts grouped by type for a sync."""
        ...
