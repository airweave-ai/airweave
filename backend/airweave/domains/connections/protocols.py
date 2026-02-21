"""Protocols for connection repository."""

from typing import Optional, Protocol, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.connection import Connection
from airweave.schemas.connection import ConnectionCreate


class ConnectionRepositoryProtocol(Protocol):
    """Access to connection records."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[Connection]:
        """Get a connection by ID within an organization."""
        ...

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, ctx: ApiContext
    ) -> Optional[Connection]:
        """Get a connection by human-readable ID within an organization."""
        ...

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: Union[ConnectionCreate, dict],
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> Connection:
        """Create a connection record."""
        ...
