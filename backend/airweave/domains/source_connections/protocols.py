"""Protocols for source connection domain.

Domain-specific: only used by source_connections service and response builder.
"""

from typing import Any, Dict, List, Optional, Protocol
from uuid import UUID

from airweave.schemas.source_connection import (
    SourceConnection,
    SourceConnectionJob,
    SourceConnectionListItem,
)


class SourceConnectionRepositoryProtocol(Protocol):
    """Data access for source connections.

    Wraps crud.source_connection for testability.
    Only includes methods the source connection domain needs.
    """

    async def get(self, db: Any, *, id: UUID, ctx: Any) -> Optional[Any]:
        """Get a source connection by ID within org scope."""
        ...

    async def get_multi_with_stats(
        self, db: Any, *, ctx: Any, collection_id: Optional[str], skip: int, limit: int
    ) -> List[Dict[str, Any]]:
        """Get source connections with stats for list endpoint."""
        ...

    async def get_by_query_and_org(self, db: Any, ctx: Any, **kwargs: Any) -> Optional[Any]:
        """Get source connection by arbitrary filters within org scope."""
        ...

    async def create(self, db: Any, *, obj_in: Any, ctx: Any, uow: Any) -> Any:
        """Create a source connection record."""
        ...

    async def update(self, db: Any, *, db_obj: Any, obj_in: Any, ctx: Any, uow: Any) -> Any:
        """Update a source connection record."""
        ...

    async def remove(self, db: Any, *, id: UUID, ctx: Any) -> Any:
        """Delete a source connection (CASCADE)."""
        ...

    async def get_schedule_info(self, db: Any, source_connection: Any) -> Optional[Dict[str, Any]]:
        """Get schedule info for a source connection."""
        ...


class ResponseBuilderProtocol(Protocol):
    """Builds API response schemas for source connections."""

    async def build_response(self, db: Any, source_conn: Any, ctx: Any) -> SourceConnection:
        """Build full SourceConnection response from ORM object."""
        ...

    def build_list_item(self, data: Dict[str, Any]) -> SourceConnectionListItem:
        """Build a SourceConnectionListItem from a stats dict."""
        ...

    def map_sync_job(self, job: Any, source_connection_id: UUID) -> SourceConnectionJob:
        """Convert sync job to SourceConnectionJob schema."""
        ...
