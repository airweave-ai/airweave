"""Fake sync cursor repository for testing."""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.models.sync_cursor import SyncCursor


class FakeSyncCursorRepository:
    """In-memory fake for SyncCursorRepositoryProtocol."""

    def __init__(self) -> None:
        """Initialize with empty store."""
        self._store: dict[UUID, SyncCursor] = {}
        self._calls: list[tuple] = []

    def seed(self, sync_id: UUID, cursor: SyncCursor) -> None:
        """Seed a cursor for a given sync_id."""
        self._store[sync_id] = cursor

    async def get_by_sync_id(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> Optional[SyncCursor]:
        """Return seeded cursor or None."""
        self._calls.append(("get_by_sync_id", db, sync_id, ctx))
        return self._store.get(sync_id)
