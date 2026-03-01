"""Concrete user repository — delegates to the existing CRUD singleton."""

from airweave import crud


class UserRepository:
    """Implements UserRepositoryProtocol by delegating to crud.user."""

    async def get_by_email(self, db, *, email):
        """Return user by email via delegated CRUD."""
        return await crud.user.get_by_email(db, email=email)

    async def update_user_no_auth(self, db, *, id, obj_in):
        """Update user without auth checks via delegated CRUD."""
        return await crud.user.update_user_no_auth(db, id=id, obj_in=obj_in)
