"""Sync repository -- wraps crud.sync.

Only includes methods the source connections domain currently needs.
"""

from typing import Any, Optional
from uuid import UUID

from airweave import crud


class SyncRepository:
    """Repository wrapping crud.sync."""

    async def get(self, db: Any, *, id: UUID, ctx: Any) -> Optional[Any]:
        """Get a sync by ID."""
        return await crud.sync.get(db, id=id, ctx=ctx)
