"""Protocol for sync cursor data access.

Cross-cutting: used by source connections, sync orchestrator.
"""

from typing import Any, Optional, Protocol
from uuid import UUID


class SyncCursorRepositoryProtocol(Protocol):
    """Data access for SyncCursor records."""

    async def get_by_sync_id(self, db: Any, *, sync_id: UUID, ctx: Any) -> Optional[Any]:
        """Get a sync cursor by sync ID."""
        ...
