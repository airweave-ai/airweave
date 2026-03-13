"""Protocols for the Connect domain."""

from typing import List, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.schemas.connect_session import (
    ConnectSessionContext,
    ConnectSessionCreate,
    ConnectSessionResponse,
)


class ConnectServiceProtocol(Protocol):
    """Service that owns all Connect business logic.

    The API endpoint is a thin router delegating to this service.
    """

    async def create_session(
        self,
        db: AsyncSession,
        session_in: ConnectSessionCreate,
        ctx: ApiContext,
    ) -> ConnectSessionResponse:
        """Create a connect session token (server-to-server, API key auth)."""
        ...

    async def list_sources(
        self,
        db: AsyncSession,
        session: ConnectSessionContext,
    ) -> List[schemas.Source]:
        """List available source integrations for the connect session."""
        ...

    async def get_source(
        self,
        db: AsyncSession,
        short_name: str,
        session: ConnectSessionContext,
    ) -> schemas.Source:
        """Get detailed info about a specific source integration."""
        ...

    async def list_source_connections(
        self,
        db: AsyncSession,
        session: ConnectSessionContext,
    ) -> List[schemas.SourceConnectionListItem]:
        """List source connections in the session's collection."""
        ...

    async def get_source_connection(
        self,
        db: AsyncSession,
        connection_id: UUID,
        session: ConnectSessionContext,
    ) -> schemas.SourceConnection:
        """Get a source connection by ID within session scope."""
        ...

    async def delete_source_connection(
        self,
        db: AsyncSession,
        connection_id: UUID,
        session: ConnectSessionContext,
    ) -> schemas.SourceConnection:
        """Delete a source connection within session scope."""
        ...

    async def create_source_connection(
        self,
        db: AsyncSession,
        source_connection_in: schemas.SourceConnectionCreate,
        session: ConnectSessionContext,
        session_token: str,
    ) -> schemas.SourceConnection:
        """Create a source connection via Connect session."""
        ...

    async def get_connection_jobs(
        self,
        db: AsyncSession,
        connection_id: UUID,
        session: ConnectSessionContext,
    ) -> List[schemas.SourceConnectionJob]:
        """Get sync jobs for a source connection within session scope."""
        ...
