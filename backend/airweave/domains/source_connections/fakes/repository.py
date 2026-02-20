"""Fake source connection repository for testing."""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.models.source_connection import SourceConnection


class FakeSourceConnectionRepository:
    """In-memory fake for SourceConnectionRepositoryProtocol."""

    def __init__(self) -> None:
        """Initialize with empty in-memory stores."""
        self._store: dict[UUID, SourceConnection] = {}
        self._org_counts: dict[UUID, int] = {}
        self._calls: list[tuple] = []

    def seed(self, id: UUID, obj: SourceConnection) -> None:
        """Seed a source connection into the store."""
        self._store[id] = obj

    def set_org_count(self, organization_id: UUID, count: int) -> None:
        """Set the count returned by count_by_organization for a given org."""
        self._org_counts[organization_id] = count

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[SourceConnection]:
        """Return the seeded source connection by ID."""
        self._calls.append(("get", db, id, ctx))
        return self._store.get(id)

    async def count_by_organization(self, db: AsyncSession, organization_id: UUID) -> int:
        """Return the seeded count for the organization."""
        self._calls.append(("count_by_organization", db, organization_id))
        return self._org_counts.get(organization_id, 0)
