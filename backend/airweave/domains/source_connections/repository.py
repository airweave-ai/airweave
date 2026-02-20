"""Source connection repository wrapping crud.source_connection."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airweave import crud
from airweave.api.context import ApiContext
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
