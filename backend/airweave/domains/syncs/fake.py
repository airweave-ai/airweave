"""Fake sync repository for testing."""

from typing import Any, Optional
from uuid import UUID


class FakeSyncRepository:
    """In-memory fake for SyncRepositoryProtocol."""

    def __init__(self) -> None:
        self._store: dict[UUID, Any] = {}

    async def get(self, db: Any, *, id: UUID, ctx: Any) -> Optional[Any]:
        """Get a sync by ID."""
        return self._store.get(id)

    def seed(self, *syncs: Any) -> None:
        """Add pre-built syncs."""
        for s in syncs:
            self._store[s.id] = s

    def clear(self) -> None:
        """Reset state."""
        self._store.clear()
