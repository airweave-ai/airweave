"""Fake sync job repository for testing."""

from typing import Any, List, Optional
from uuid import UUID


class FakeSyncJobRepository:
    """In-memory fake for SyncJobRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[UUID, Any] = {}

    async def get(self, db: Any, *, id: UUID, ctx: Any) -> Optional[Any]:
        """Get a sync job by ID."""
        return self._store.get(id)

    async def get_latest_by_sync_id(self, db: Any, *, sync_id: UUID) -> Optional[Any]:
        """Get the most recent sync job for a sync."""
        matching = [j for j in self._store.values() if getattr(j, "sync_id", None) == sync_id]
        if not matching:
            return None
        return max(matching, key=lambda j: getattr(j, "created_at", 0))

    async def get_all_by_sync_id(self, db: Any, *, sync_id: UUID) -> List[Any]:
        """Get all sync jobs for a sync."""
        return [j for j in self._store.values() if getattr(j, "sync_id", None) == sync_id]

    def seed(self, *jobs: Any) -> None:
        """Add pre-built sync jobs."""
        for job in jobs:
            self._store[job.id] = job

    def clear(self) -> None:
        """Reset state."""
        self._store.clear()
