"""Connection repository -- wraps crud.connection.

Only includes methods source connections currently needs.
"""

from typing import Any, Optional
from uuid import UUID

from airweave import crud


class ConnectionRepository:
    """Repository wrapping crud.connection."""

    async def create(self, db: Any, *, obj_in: Any, ctx: Any, uow: Any) -> Any:
        """Create a connection record."""
        return await crud.connection.create(db, obj_in=obj_in, ctx=ctx, uow=uow)

    async def get(self, db: Any, *, id: UUID, ctx: Any) -> Optional[Any]:
        """Get a connection by ID."""
        return await crud.connection.get(db, id=id, ctx=ctx)

    async def get_by_readable_id(self, db: Any, *, readable_id: str, ctx: Any) -> Optional[Any]:
        """Get a connection by readable ID."""
        return await crud.connection.get_by_readable_id(db, readable_id=readable_id, ctx=ctx)
