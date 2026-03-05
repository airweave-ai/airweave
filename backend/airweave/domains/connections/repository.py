"""Connection repository wrapping crud.connection."""

from typing import Optional, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.core.shared_models import IntegrationType
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.connections.protocols import ConnectionRepositoryProtocol
from airweave.models.connection import Connection
from airweave.schemas.connection import ConnectionCreate, ConnectionUpdate


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

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: ConnectionCreate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Connection:
        return await crud.connection.create(db, obj_in=obj_in, ctx=ctx, uow=uow)

    async def get_by_integration_type(
        self, db: AsyncSession, *, integration_type: IntegrationType, ctx: ApiContext
    ) -> list[Connection]:
        return await crud.connection.get_by_integration_type(
            db, integration_type=integration_type, ctx=ctx
        )

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: Connection,
        obj_in: Union[ConnectionUpdate, dict],
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Connection:
        return await crud.connection.update(db, db_obj=db_obj, obj_in=obj_in, ctx=ctx, uow=uow)

    async def remove(self, db: AsyncSession, *, id: UUID, ctx: ApiContext) -> Optional[Connection]:
        return await crud.connection.remove(db, id=id, ctx=ctx)
