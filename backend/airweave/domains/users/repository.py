"""Concrete user repository — delegates to the existing CRUD singleton."""

from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airweave import crud, schemas
from airweave.domains.users.protocols import UserRepositoryProtocol
from airweave.models.organization import Organization
from airweave.models.user import User
from airweave.models.user_organization import UserOrganization


class UserRepository(UserRepositoryProtocol):
    """Implements UserRepositoryProtocol by delegating to crud.user."""

    @staticmethod
    def _user_query_with_orgs() -> Select[tuple[User]]:
        """Query that eagerly loads user -> user_organizations -> organization -> feature_flags."""
        return select(User).options(
            selectinload(User.user_organizations)
            .selectinload(UserOrganization.organization)
            .options(selectinload(Organization.feature_flags))
        )

    async def get_by_email(self, db: AsyncSession, *, email: str) -> Any:
        """Return user by email via delegated CRUD."""
        return await crud.user.get_by_email(db, email=email)

    async def create(self, db: AsyncSession, *, obj_in: schemas.UserCreate) -> User:
        """Create a new user and flush."""
        user = User(**obj_in.model_dump())
        db.add(user)
        await db.flush()
        return user

    async def refresh(self, db: AsyncSession, *, user: User) -> User:
        """Reload a user from the database with all relationships.

        Uses an explicit selectinload query instead of bare db.refresh()
        so that user_organizations -> organization -> feature_flags are
        fully populated for Pydantic serialization.
        """
        stmt = self._user_query_with_orgs().where(User.id == user.id)
        result = await db.execute(stmt)
        refreshed = result.unique().scalar_one_or_none()
        return refreshed or user

    async def update_user_no_auth(
        self, db: AsyncSession, *, id: UUID, obj_in: schemas.UserUpdate
    ) -> Any:
        """Update user without auth checks via delegated CRUD."""
        return await crud.user.update_user_no_auth(db, id=id, obj_in=obj_in)
