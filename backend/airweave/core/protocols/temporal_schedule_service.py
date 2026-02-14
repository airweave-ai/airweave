"""Protocol for Temporal schedule management.

Cross-cutting: used by source connections.
"""

from typing import Any, Protocol
from uuid import UUID


class TemporalScheduleServiceProtocol(Protocol):
    """Temporal schedule create/update."""

    async def create_or_update_schedule(
        self,
        sync_id: UUID,
        cron_schedule: str,
        db: Any,
        ctx: Any,
        uow: Any,
    ) -> str:
        """Create or update a Temporal cron schedule for a sync."""
        ...
