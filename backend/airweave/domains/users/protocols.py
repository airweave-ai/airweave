"""Protocols for the users domain."""

from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.domains.users.types import CreateOrUpdateResult
from airweave.models.user import User

# ---------------------------------------------------------------------------
# Repository protocols
# ---------------------------------------------------------------------------


class UserRepositoryProtocol(Protocol):
    """User lookup and activity tracking used by context resolution."""

    async def get_by_email(self, db: AsyncSession, *, email: str) -> Any:
        """Return user ORM model by email, or raise NotFoundException."""
        ...

    async def create(self, db: AsyncSession, *, obj_in: schemas.UserCreate) -> User:
        """Create a new user and flush. Returns ORM model."""
        ...

    async def refresh(self, db: AsyncSession, *, user: User) -> User:
        """Reload a user from the database (including relationships)."""
        ...

    async def update_user_no_auth(
        self, db: AsyncSession, *, id: UUID, obj_in: schemas.UserUpdate
    ) -> Any:
        """Update user fields without auth context. Returns ORM model."""
        ...


# ---------------------------------------------------------------------------
# Service protocol (single facade consumed by API layer)
# ---------------------------------------------------------------------------


class UserServiceProtocol(Protocol):
    """User domain service used by API endpoints.

    Covers user creation/update with Auth0 integration and org queries.
    """

    async def create_or_update(
        self,
        db: AsyncSession,
        user_data: schemas.UserCreate,
        auth0_user: Any,
    ) -> CreateOrUpdateResult:
        """Create or update a user, syncing Auth0 organizations.

        Returns a result indicating the user and whether they are new.
        Raises ValueError on auth0 ID conflict.
        """
        ...

    async def get_user_organizations(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> list[schemas.OrganizationWithRole]:
        """Return all organizations the user belongs to, with roles."""
        ...
