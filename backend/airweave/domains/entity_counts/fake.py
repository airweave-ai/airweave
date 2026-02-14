"""Fake entity count repository for testing."""

from typing import Any, List
from uuid import UUID


class FakeEntityCountRepository:
    """In-memory fake for EntityCountRepositoryProtocol."""

    def __init__(self) -> None:
        self._by_sync_id: dict[UUID, List[Any]] = {}

    async def get_counts_per_sync_and_type(self, db: Any, sync_id: UUID) -> List[Any]:
        """Get entity counts grouped by type for a sync."""
        return self._by_sync_id.get(sync_id, [])

    def seed(self, sync_id: UUID, counts: List[Any]) -> None:
        """Add pre-built entity counts."""
        self._by_sync_id[sync_id] = counts

    def clear(self) -> None:
        """Reset state."""
        self._by_sync_id.clear()
