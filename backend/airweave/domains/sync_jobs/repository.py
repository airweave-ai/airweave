"""Sync job repository -- wraps crud.sync_job.

Only includes methods the source connections domain currently needs.
"""

from typing import Any, List, Optional
from uuid import UUID

from airweave import crud


class SyncJobRepository:
    """Repository wrapping crud.sync_job."""

    async def get(self, db: Any, *, id: UUID, ctx: Any) -> Optional[Any]:
        """Get a sync job by ID."""
        return await crud.sync_job.get(db, id=id, ctx=ctx)

    async def get_latest_by_sync_id(self, db: Any, *, sync_id: UUID) -> Optional[Any]:
        """Get the most recent sync job for a sync."""
        return await crud.sync_job.get_latest_by_sync_id(db, sync_id=sync_id)

    async def get_all_by_sync_id(self, db: Any, *, sync_id: UUID) -> List[Any]:
        """Get all sync jobs for a sync."""
        return await crud.sync_job.get_all_by_sync_id(db, sync_id=sync_id)
