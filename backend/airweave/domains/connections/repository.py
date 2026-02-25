"""Connection repository wrapping crud.connection."""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.domains.connections.protocols import ConnectionRepositoryProtocol
from airweave.models.connection import Connection, IntegrationType


class ConnectionRepository(ConnectionRepositoryProtocol):
    """Delegates to the crud.connection singleton."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[Connection]:
        return await crud.connection.get(db, id, ctx)

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, ctx: ApiContext
    ) -> Optional[Connection]:
        return await crud.connection.get_by_readable_id(db, readable_id=readable_id, ctx=ctx)

    async def get_s3_destination_for_org(
        self, db: AsyncSession, ctx: ApiContext
    ) -> Optional[Connection]:
        connections = await crud.connection.get_all_by_short_name(db, short_name="s3", ctx=ctx)
        for connection in connections:
            if connection.integration_type == IntegrationType.DESTINATION:
                return connection
        return None
