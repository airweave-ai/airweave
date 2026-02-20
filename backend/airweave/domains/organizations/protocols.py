"""Protocols for organization domain repositories."""

from typing import Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.models.organization import Organization


class OrganizationRepositoryProtocol(Protocol):
    """Read-only access to organization records."""

    async def get_by_id(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        skip_access_validation: bool = False,
    ) -> Optional[Organization]:
        """Get organization by ID."""
        ...


class UserOrganizationRepositoryProtocol(Protocol):
    """Read-only access to user-organization membership records."""

    async def count_members(self, db: AsyncSession, organization_id: UUID) -> int:
        """Count members belonging to an organization."""
        ...
