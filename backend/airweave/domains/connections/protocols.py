"""Protocols for connection repository."""

from typing import Optional, Protocol, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.shared_models import IntegrationType
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.connection import Connection
from airweave.schemas.connection import ConnectionCreate, ConnectionUpdate


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

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: ConnectionCreate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Connection:
        """Create a connection."""
        ...

    async def get_by_integration_type(
        self, db: AsyncSession, *, integration_type: IntegrationType, ctx: ApiContext
    ) -> list[Connection]:
        """Get org-scoped connections filtered by integration type."""
        ...

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: Connection,
        obj_in: Union[ConnectionUpdate, dict],
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Connection:
        """Update a connection."""
        ...

    async def remove(self, db: AsyncSession, *, id: UUID, ctx: ApiContext) -> Optional[Connection]:
        """Delete a connection by ID."""
        ...
