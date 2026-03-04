"""Fake entity count repository for testing."""

from typing import List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.schemas.entity_count import EntityCountWithDefinition


class FakeEntityCountRepository:
    """In-memory fake for EntityCountRepositoryProtocol."""

    def __init__(self) -> None:
        """Initialize with empty store."""
        self._store: dict[UUID, List[EntityCountWithDefinition]] = {}
        self._calls: list[tuple] = []

    def seed(self, sync_id: UUID, counts: List[EntityCountWithDefinition]) -> None:
        """Seed entity counts for a given sync_id."""
        self._store[sync_id] = counts

    async def get_counts_per_sync_and_type(
        self, db: AsyncSession, sync_id: UUID
    ) -> List[EntityCountWithDefinition]:
        """Return seeded counts or empty list."""
        self._calls.append(("get_counts_per_sync_and_type", db, sync_id))
        return self._store.get(sync_id, [])
