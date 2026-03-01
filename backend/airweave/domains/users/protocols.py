"""Repository protocols for the users domain."""

from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas


class UserRepositoryProtocol(Protocol):
    """User lookup and activity tracking used by context resolution."""

    async def get_by_email(self, db: AsyncSession, *, email: str) -> Any:
        """Return user ORM model by email, or raise NotFoundException."""
        ...

    async def update_user_no_auth(
        self, db: AsyncSession, *, id: UUID, obj_in: schemas.UserUpdate
    ) -> Any:
        """Update user fields without auth context. Returns ORM model."""
        ...
