"""Protocol for sync service operations.

Cross-cutting: used by source connections, admin.
"""

from typing import Any, Dict, List, Optional, Protocol, Tuple
from uuid import UUID


class SyncServiceProtocol(Protocol):
    """Sync lifecycle operations."""

    async def list_sync_jobs(self, db: Any, ctx: Any, sync_id: UUID, limit: int = 100) -> List[Any]:
        """List sync jobs for a sync."""
        ...

    async def trigger_sync_run(
        self,
        db: Any,
        sync_id: UUID,
        ctx: Any,
        execution_config: Optional[Dict[str, Any]] = None,
        sync_metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Any, Any]:
        """Trigger a sync run, returns (sync, sync_job)."""
        ...

    async def get_last_sync_job(self, db: Any, ctx: Any, sync_id: UUID) -> Optional[Any]:
        """Get the most recent sync job for a sync."""
        ...
