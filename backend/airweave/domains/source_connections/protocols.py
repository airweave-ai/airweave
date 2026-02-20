"""Protocols for source connection repository."""

from typing import Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.models.source_connection import SourceConnection


class SourceConnectionRepositoryProtocol(Protocol):
    """Read-only access to source connection records."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[SourceConnection]:
        """Get a source connection by ID within an organization."""
        ...

    async def count_by_organization(self, db: AsyncSession, organization_id: UUID) -> int:
        """Count source connections belonging to an organization."""
        ...
