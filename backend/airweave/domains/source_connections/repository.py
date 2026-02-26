"""Source connection repository wrapping crud.source_connection."""

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airweave import crud
from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.source_connections.protocols import SourceConnectionRepositoryProtocol
from airweave.domains.source_connections.types import ScheduleInfo, SourceConnectionStats
from airweave.models.connection_init_session import ConnectionInitSession
from airweave.models.source_connection import SourceConnection


class SourceConnectionRepository(SourceConnectionRepositoryProtocol):
    """Delegates to the crud.source_connection singleton."""

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[SourceConnection]:
        """Get a source connection by ID within org scope."""
        return await crud.source_connection.get(db, id, ctx)

    async def get_by_sync_id(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> Optional[SourceConnection]:
        """Get a source connection by sync ID within org scope."""
        return await crud.source_connection.get_by_sync_id(db, sync_id=sync_id, ctx=ctx)

    async def get_schedule_info(
        self, db: AsyncSession, source_connection: SourceConnection
    ) -> Optional[ScheduleInfo]:
        """Get schedule info for a source connection."""
        return await crud.source_connection.get_schedule_info(db, source_connection)

    async def get_by_init_session(
        self, db: AsyncSession, *, init_session_id: UUID, ctx: ApiContext
    ) -> Optional[SourceConnection]:
        """Get source connection by init session ID within org scope."""
        return await crud.source_connection.get_by_query_and_org(
            db, ctx=ctx, connection_init_session_id=init_session_id
        )

    async def get_init_session_with_redirect(
        self, db: AsyncSession, session_id: UUID, ctx: ApiContext
    ) -> Optional[ConnectionInitSession]:
        """Get a ConnectionInitSession by ID with redirect_session eagerly loaded."""
        stmt = (
            select(ConnectionInitSession)
            .where(ConnectionInitSession.id == session_id)
            .where(ConnectionInitSession.organization_id == ctx.organization.id)
            .options(selectinload(ConnectionInitSession.redirect_session))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi_with_stats(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        collection_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SourceConnectionStats]:
        """Get source connections with complete stats."""
        raw = await crud.source_connection.get_multi_with_stats(
            db, ctx=ctx, collection_id=collection_id, skip=skip, limit=limit
        )
        return [SourceConnectionStats.from_dict(d) for d in raw]

    async def get_sync_ids_for_collection(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        readable_collection_id: str,
    ) -> List[UUID]:
        """Get all sync IDs for source connections in a collection."""
        rows = await db.execute(
            select(SourceConnection.sync_id)
            .where(
                SourceConnection.organization_id == organization_id,
                SourceConnection.readable_collection_id == readable_collection_id,
                SourceConnection.sync_id.is_not(None),
            )
            .distinct()
        )
        return [row[0] for row in rows if row[0]]

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: SourceConnection,
        obj_in: dict[str, Any],
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> SourceConnection:
        """Update a source connection."""
        return await crud.source_connection.update(
            db, db_obj=db_obj, obj_in=obj_in, ctx=ctx, uow=uow
        )

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: dict[str, Any],
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> SourceConnection:
        """Create a source connection."""
        return await crud.source_connection.create(db, obj_in=obj_in, ctx=ctx, uow=uow)

    async def remove(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
    ) -> Optional[SourceConnection]:
        """Delete a source connection by ID."""
        return await crud.source_connection.remove(db, id=id, ctx=ctx)
