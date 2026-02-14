"""Sync cursor repository -- wraps crud.sync_cursor.

Only includes methods the source connections domain currently needs.
"""

from typing import Any, Optional
from uuid import UUID

from airweave import crud


class SyncCursorRepository:
    """Repository wrapping crud.sync_cursor."""

    async def get_by_sync_id(self, db: Any, *, sync_id: UUID, ctx: Any) -> Optional[Any]:
        """Get a sync cursor by sync ID."""
        return await crud.sync_cursor.get_by_sync_id(db, sync_id=sync_id, ctx=ctx)
