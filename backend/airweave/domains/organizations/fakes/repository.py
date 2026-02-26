"""Fake organization repository for testing."""

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
