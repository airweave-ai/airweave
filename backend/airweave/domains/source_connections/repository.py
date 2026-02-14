"""Source connection repository -- wraps crud.source_connection.

Thin data-access layer for testability. Only includes methods
the source connection domain currently needs.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from airweave import crud


class SourceConnectionRepository:
    """Repository wrapping crud.source_connection."""

    async def get(self, db: Any, *, id: UUID, ctx: Any) -> Optional[Any]:
        """Get a source connection by ID within org scope."""
        return await crud.source_connection.get(db, id=id, ctx=ctx)

    async def get_multi_with_stats(
        self, db: Any, *, ctx: Any, collection_id: Optional[str], skip: int, limit: int
    ) -> List[Dict[str, Any]]:
        """Get source connections with stats for list endpoint."""
        return await crud.source_connection.get_multi_with_stats(
            db, ctx=ctx, collection_id=collection_id, skip=skip, limit=limit
        )

    async def get_by_query_and_org(self, db: Any, ctx: Any, **kwargs: Any) -> Optional[Any]:
        """Get source connection by arbitrary filters within org scope."""
        return await crud.source_connection.get_by_query_and_org(db, ctx=ctx, **kwargs)

    async def create(self, db: Any, *, obj_in: Any, ctx: Any, uow: Any) -> Any:
        """Create a source connection record."""
        return await crud.source_connection.create(db, obj_in=obj_in, ctx=ctx, uow=uow)

    async def update(self, db: Any, *, db_obj: Any, obj_in: Any, ctx: Any, uow: Any) -> Any:
        """Update a source connection record."""
        return await crud.source_connection.update(
            db, db_obj=db_obj, obj_in=obj_in, ctx=ctx, uow=uow
        )

    async def remove(self, db: Any, *, id: UUID, ctx: Any) -> Any:
        """Delete a source connection (CASCADE)."""
        return await crud.source_connection.remove(db, id=id, ctx=ctx)

    async def get_schedule_info(self, db: Any, source_connection: Any) -> Optional[Dict[str, Any]]:
        """Get schedule info for a source connection."""
        return await crud.source_connection.get_schedule_info(db, source_connection)
