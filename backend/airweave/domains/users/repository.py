"""Concrete user repository — delegates to the existing CRUD singleton."""

from airweave import crud, schemas
from airweave.domains.users.protocols import UserRepositoryProtocol
from airweave.models.user import User


class UserRepository(UserRepositoryProtocol):
    """Implements UserRepositoryProtocol by delegating to crud.user."""

    async def get_by_email(self, db, *, email):
        """Return user by email via delegated CRUD."""
        return await crud.user.get_by_email(db, email=email)

    async def create(self, db, *, obj_in: schemas.UserCreate) -> User:
        """Create a new user and flush."""
        user = User(**obj_in.model_dump())
        db.add(user)
        await db.flush()
        return user

    async def refresh(self, db, *, user: User) -> User:
        """Reload a user from the database (including relationships)."""
        await db.refresh(user)
        return user

    async def update_user_no_auth(self, db, *, id, obj_in):
        """Update user without auth checks via delegated CRUD."""
        return await crud.user.update_user_no_auth(db, id=id, obj_in=obj_in)
