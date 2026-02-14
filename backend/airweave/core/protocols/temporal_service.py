"""Protocol for Temporal workflow operations.

Cross-cutting: used by source connections, admin, sync orchestrator.
"""

from typing import Any, List, Optional, Protocol


class TemporalServiceProtocol(Protocol):
    """Temporal workflow management."""

    async def run_source_connection_workflow(
        self,
        sync: Any,
        sync_job: Any,
        collection: Any,
        connection: Any,
        ctx: Any,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
    ) -> Any:
        """Start a sync workflow in Temporal."""
        ...

    async def cancel_sync_job_workflow(self, sync_job_id: str, ctx: Any) -> dict:
        """Request cancellation of a running sync workflow."""
        ...

    async def start_cleanup_sync_data_workflow(
        self,
        sync_ids: List[str],
        collection_id: str,
        organization_id: str,
        ctx: Any,
    ) -> Optional[Any]:
        """Start async cleanup of external data (Vespa, ARF)."""
        ...
