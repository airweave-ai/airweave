"""Protocols for collection repository."""

from typing import Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.models.collection import Collection


class CollectionRepositoryProtocol(Protocol):
    """Read-only access to collection records."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[Collection]:
        """Get a collection by ID within an organization."""
        ...

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, ctx: ApiContext
    ) -> Optional[Collection]:
        """Get a collection by human-readable ID within an organization."""
        ...
