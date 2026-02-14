"""Protocol for sync job data access.

Cross-cutting: used by source connections, sync service, admin.
"""

from typing import Any, List, Optional, Protocol
from uuid import UUID


class SyncJobRepositoryProtocol(Protocol):
    """Data access for SyncJob records."""

    async def get(self, db: Any, *, id: UUID, ctx: Any) -> Optional[Any]:
        """Get a sync job by ID."""
        ...

    async def get_latest_by_sync_id(self, db: Any, *, sync_id: UUID) -> Optional[Any]:
        """Get the most recent sync job for a sync."""
        ...

    async def get_all_by_sync_id(self, db: Any, *, sync_id: UUID) -> List[Any]:
        """Get all sync jobs for a sync."""
        ...
