"""Organization domain repositories."""

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.domains.organizations.protocols import (
    OrganizationRepositoryProtocol,
    UserOrganizationRepositoryProtocol,
)
from airweave.models.organization import Organization
from airweave.models.user_organization import UserOrganization


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


class UserOrganizationRepository(UserOrganizationRepositoryProtocol):
    """Counts organization members via direct query."""

    async def count_members(self, db: AsyncSession, organization_id: UUID) -> int:
        """Count members in the organization."""
        stmt = (
            select(func.count())
            .select_from(UserOrganization)
            .where(UserOrganization.organization_id == organization_id)
        )
        result = await db.execute(stmt)
        return int(result.scalar_one() or 0)
