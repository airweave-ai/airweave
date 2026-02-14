"""Fake sync cursor repository for testing."""

from typing import Any, Optional
from uuid import UUID


class FakeSyncCursorRepository:
    """In-memory fake for SyncCursorRepositoryProtocol."""

    def __init__(self) -> None:
        self._by_sync_id: dict[UUID, Any] = {}

    async def get_by_sync_id(self, db: Any, *, sync_id: UUID, ctx: Any) -> Optional[Any]:
        """Get a sync cursor by sync ID."""
        return self._by_sync_id.get(sync_id)

    def seed(self, sync_id: UUID, cursor: Any) -> None:
        """Add a pre-built cursor."""
        self._by_sync_id[sync_id] = cursor

    def clear(self) -> None:
        """Reset state."""
        self._by_sync_id.clear()
