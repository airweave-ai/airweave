"""Protocol for sync job status management.

Cross-cutting: used by source connections, sync orchestrator.
"""

from datetime import datetime
from typing import Any, Optional, Protocol
from uuid import UUID


class SyncJobServiceProtocol(Protocol):
    """Sync job status updates."""

    async def update_status(
        self,
        sync_job_id: UUID,
        status: Any,
        ctx: Any,
        stats: Optional[Any] = None,
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
    ) -> None:
        """Update the status of a sync job."""
        ...
