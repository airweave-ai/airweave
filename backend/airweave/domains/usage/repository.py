"""Usage domain repository wrapping crud.usage."""

from typing import Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.core.context import BaseContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.usage.types import ActionType
from airweave.models.usage import Usage
from airweave.schemas.usage import UsageCreate


class UsageRepositoryProtocol(Protocol):
    """Data access for usage records."""

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: UsageCreate,
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Usage:
        """Create a usage record."""
        ...

    async def get_current_usage(
        self, db: AsyncSession, *, organization_id: UUID
    ) -> Optional[Usage]:
        """Get the usage record for the current active billing period."""
        ...

    async def increment_usage(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        increments: dict[ActionType, int],
    ) -> Optional[Usage]:
        """Atomically increment usage counters and return the updated record."""
        ...

    async def get_by_billing_period(
        self, db: AsyncSession, *, billing_period_id: UUID
    ) -> Optional[Usage]:
        """Get usage record by billing period ID."""
        ...

    async def get_all_by_organization(
        self, db: AsyncSession, *, organization_id: UUID
    ) -> list[Usage]:
        """Get all usage records for an organization."""
        ...

    async def get_current_usage_for_orgs(
        self, db: AsyncSession, *, organization_ids: list[UUID]
    ) -> dict[UUID, Usage]:
        """Get current usage for multiple organizations."""
        ...


class UsageRepository(UsageRepositoryProtocol):
    """Delegates to the crud.usage singleton."""

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: UsageCreate,
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Usage:
        """Create a usage record."""
        return await crud.usage.create(db, obj_in=obj_in, ctx=ctx, uow=uow)

    async def get_current_usage(
        self, db: AsyncSession, *, organization_id: UUID
    ) -> Optional[Usage]:
        """Get the usage record for the current active billing period."""
        return await crud.usage.get_current_usage(db, organization_id=organization_id)

    async def increment_usage(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        increments: dict[ActionType, int],
    ) -> Optional[Usage]:
        """Atomically increment usage counters and return the updated record."""
        return await crud.usage.increment_usage(
            db, organization_id=organization_id, increments=increments
        )

    async def get_by_billing_period(
        self, db: AsyncSession, *, billing_period_id: UUID
    ) -> Optional[Usage]:
        """Get usage record by billing period ID."""
        return await crud.usage.get_by_billing_period(db, billing_period_id=billing_period_id)

    async def get_all_by_organization(
        self, db: AsyncSession, *, organization_id: UUID
    ) -> list[Usage]:
        """Get all usage records for an organization."""
        return await crud.usage.get_all_by_organization(db, organization_id=organization_id)

    async def get_current_usage_for_orgs(
        self, db: AsyncSession, *, organization_ids: list[UUID]
    ) -> dict[UUID, Usage]:
        """Get current usage for multiple organizations."""
        return await crud.usage.get_current_usage_for_orgs(db, organization_ids=organization_ids)
