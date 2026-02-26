"""Organization repository and protocol."""

from typing import Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
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


class OrganizationRepository(OrganizationRepositoryProtocol):
    """Delegates to the crud.organization singleton."""

    async def get_by_id(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        skip_access_validation: bool = False,
    ) -> Optional[Organization]:
        """Get organization by ID."""
        return await crud.organization.get(
            db, organization_id, skip_access_validation=skip_access_validation
        )
