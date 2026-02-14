"""Protocol for sync data access.

Cross-cutting: used by source connections, sync service, admin.
"""

from typing import Any, Optional, Protocol
from uuid import UUID


class SyncRepositoryProtocol(Protocol):
    """Data access for Sync records."""

    async def get(self, db: Any, *, id: UUID, ctx: Any) -> Optional[Any]:
        """Get a sync by ID."""
        ...
