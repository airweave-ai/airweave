"""Usage repository and protocol."""

from typing import Optional, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.usage import Usage
from airweave.schemas.usage import UsageCreate


class UsageRepositoryProtocol(Protocol):
    """Access to usage records."""

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: UsageCreate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Usage:
        """Create a usage record."""
        ...


class UsageRepository(UsageRepositoryProtocol):
    """Delegates to the crud.usage singleton."""

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: UsageCreate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Usage:
        """Create a usage record."""
        return await crud.usage.create(db, obj_in=obj_in, ctx=ctx, uow=uow)
