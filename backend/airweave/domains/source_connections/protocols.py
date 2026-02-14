"""Protocols for source connection domain.

Domain-specific: only used by source_connections service and response builder.
"""

from typing import Any, Dict, List, Optional, Protocol, Tuple
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


class SourceConnectionServiceProtocol(Protocol):
    """Source connection service protocol for DI injection."""

    async def create(self, db: Any, *, obj_in: Any, ctx: Any) -> SourceConnection: ...
    async def get(self, db: Any, *, id: UUID, ctx: Any) -> SourceConnection: ...
    async def list(
        self, db: Any, *, ctx: Any, readable_collection_id: Optional[str], skip: int, limit: int
    ) -> List[SourceConnectionListItem]: ...
    async def update(self, db: Any, *, id: UUID, obj_in: Any, ctx: Any) -> SourceConnection: ...
    async def delete(self, db: Any, *, id: UUID, ctx: Any) -> SourceConnection: ...
    async def run(
        self, db: Any, *, id: UUID, ctx: Any, force_full_sync: bool
    ) -> SourceConnectionJob: ...
    async def get_jobs(
        self, db: Any, *, id: UUID, ctx: Any, limit: int
    ) -> List[SourceConnectionJob]: ...
    async def cancel_job(
        self, db: Any, *, source_connection_id: UUID, job_id: UUID, ctx: Any
    ) -> SourceConnectionJob: ...
    async def complete_oauth1_callback(
        self, db: Any, *, oauth_token: str, oauth_verifier: str
    ) -> SourceConnection: ...
    async def complete_oauth2_callback(
        self, db: Any, *, state: str, code: str
    ) -> SourceConnection: ...


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


class SourceConnectionHelpersProtocol(Protocol):
    """Stopgap protocol wrapping source_connection_service_helpers.

    These functions will eventually be absorbed into proper domain services.
    For now, this protocol makes them injectable and fakeable for testing.
    """

    async def update_auth_fields(
        self, db: Any, source_conn: Any, auth_fields: Any, ctx: Any, uow: Any
    ) -> None: ...

    async def get_connection_for_source_connection(
        self, db: Any, source_connection: Any, ctx: Any
    ) -> Any: ...

    async def update_sync_schedule(
        self, db: Any, sync_id: UUID, cron_schedule: Optional[str], ctx: Any, uow: Any
    ) -> None: ...

    async def create_sync_without_schedule(
        self,
        db: Any,
        name: str,
        connection_id: UUID,
        collection_id: UUID,
        collection_readable_id: str,
        cron_schedule: Optional[str],
        run_immediately: bool,
        ctx: Any,
        uow: Any,
    ) -> Tuple[Any, Optional[Any]]: ...

    async def reconstruct_context_from_session(self, db: Any, init_session: Any) -> Any: ...

    async def complete_oauth1_connection(
        self, db: Any, source_conn_shell: Any, init_session: Any, token_response: Any, ctx: Any
    ) -> Any: ...

    async def complete_oauth2_connection(
        self, db: Any, source_conn_shell: Any, init_session: Any, token_response: Any, ctx: Any
    ) -> Any: ...

    async def create_connection(
        self, db: Any, name: str, source: Any, credential_id: Optional[UUID], ctx: Any, uow: Any
    ) -> Any: ...

    async def create_source_connection(
        self,
        db: Any,
        obj_in: Any,
        connection_id: Optional[UUID],
        collection_id: str,
        sync_id: Optional[UUID],
        config_fields: Optional[Dict[str, Any]],
        is_authenticated: bool,
        ctx: Any,
        uow: Any,
        auth_provider_id: Optional[str] = None,
        auth_provider_config: Optional[Dict[str, Any]] = None,
    ) -> Any: ...

    async def get_collection(self, db: Any, collection_id: str, ctx: Any) -> Any: ...
