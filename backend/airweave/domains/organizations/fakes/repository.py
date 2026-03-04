"""Fake organization repositories for testing."""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.models.organization import Organization


class FakeOrganizationRepository:
    """In-memory fake for OrganizationRepositoryProtocol."""

    def __init__(self) -> None:
        """Initialize with empty store and call log."""
        self._store: dict[UUID, Organization] = {}
        self._calls: list[tuple] = []

    def seed(self, organization_id: UUID, obj: Organization) -> None:
        """Populate store with test data."""
        self._store[organization_id] = obj

    async def get_by_id(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        skip_access_validation: bool = False,
    ) -> Optional[Organization]:
        """Get organization by ID."""
        self._calls.append(("get_by_id", db, organization_id, skip_access_validation))
        return self._store.get(organization_id)


class FakeUserOrganizationRepository:
    """In-memory fake for UserOrganizationRepositoryProtocol."""

    def __init__(self, default_count: int = 0) -> None:
        """Initialize with configurable counts and call log."""
        self._counts: dict[UUID, int] = {}
        self._default_count = default_count
        self._calls: list[tuple] = []

    def set_count(self, organization_id: UUID, count: int) -> None:
        """Set the member count for a given organization."""
        self._counts[organization_id] = count

    async def count_members(self, db: AsyncSession, organization_id: UUID) -> int:
        """Return the seeded member count for the organization."""
        self._calls.append(("count_members", db, organization_id))
        return self._counts.get(organization_id, self._default_count)
