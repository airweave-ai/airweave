"""Protocols for connection repository."""

from typing import Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.models.connection import Connection


class ConnectionRepositoryProtocol(Protocol):
    """Read-only access to connection records."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[Connection]:
        """Get a connection by ID within an organization."""
        ...

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, ctx: ApiContext
    ) -> Optional[Connection]:
        """Get a connection by human-readable ID within an organization."""
        ...

    async def get_s3_destination_for_org(
        self, db: AsyncSession, ctx: ApiContext
    ) -> Optional[Connection]:
        """Get the org-scoped S3 destination connection if configured."""
        ...
