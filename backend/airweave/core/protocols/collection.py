"""Protocol for collection data access.

Cross-cutting: used by source connections, search, collection service.
"""

from typing import Any, Optional, Protocol


class CollectionRepositoryProtocol(Protocol):
    """Data access for Collection records."""

    async def get_by_readable_id(self, db: Any, *, readable_id: str, ctx: Any) -> Optional[Any]:
        """Get a collection by readable ID."""
        ...
