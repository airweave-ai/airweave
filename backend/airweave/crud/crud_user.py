"""The CRUD operations for the User model."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airweave.crud._base import CRUDBase
from airweave.models.api_key import APIKey
from airweave.models.user import User
from airweave.schemas.user import UserCreate, UserUpdate


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    """CRUD operations for the User model."""

    async def get_by_email(self, db: AsyncSession, *, email: str) -> Optional[User]:
        """Get a user by email.

        Important: this method is not part of the regular CRUD operations.
        This is a custom method for getting a user by email, that does not
        require a current user. Use responsibly.

        Args:
            db (AsyncSession): The database session.
            email (str): The email of the user to get.

        Returns:
            Optional[User]: The user with the given email.
        """
        # Use selectinload to eagerly load the organization
        stmt = select(User).where(User.email == email).options(selectinload(User.organization))
        result = await db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get(self, db: AsyncSession, id: UUID, current_user: User) -> Optional[User]:
        """Get a single object by ID.

        Args:
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to get. Doesn't require strict typing.
            current_user (User): The current user.

        Returns:
            Optional[User]: The user with the given ID.
        """
        # Use selectinload to eagerly load the organization
        stmt = select(User).where(User.id == id).options(selectinload(User.organization))
        result = await db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_multi(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> list[User]:
        """Get multiple objects.

        WARNING: This method is not secure and should not be used in production.
        It is only used for MLOps and testing purposes.

        TODO: Implement proper security measures through admin roles.

        Args:
            db (AsyncSession): The database session.
            skip (int): The number of objects to skip.
            limit (int): The number of objects to return.

        Returns:
            list[User]: A list of users.
        """
        # Use selectinload to eagerly load the organization for all users
        stmt = select(User).offset(skip).limit(limit).options(selectinload(User.organization))
        result = await db.execute(stmt)
        return list(result.unique().scalars().all())

    async def create(self, db: AsyncSession, *, obj_in: UserCreate) -> User:
        """Create a new user.

        Always creates a default organization for the user if one is not provided.

        Args:
            db (AsyncSession): The database session.
            obj_in (UserCreate): The object to create.

        Returns:
            User: The newly created user.
        """
        # Always create an organization for the user if one is not provided
        if not hasattr(obj_in, "organization_id") or obj_in.organization_id is None:
            from airweave.crud.crud_organization import organization as crud_organization
            from airweave.schemas.organization import OrganizationCreate

            org_name = f"Organization for {obj_in.email}"

            # Check if an organization with this name already exists
            existing_org = await crud_organization.get_by_name(db, name=org_name)
            if existing_org:
                # Use the existing organization
                org_id = existing_org.id
            else:
                # Create a new organization
                org_in = OrganizationCreate(
                    name=org_name, description=f"Auto-created organization for {obj_in.email}"
                )
                org = await crud_organization.create(db, obj_in=org_in)
                org_id = org.id

            # Update the user create object with the organization
            user_data = obj_in.model_dump()
            user_data["organization_id"] = org_id
            obj_in = UserCreate(**user_data)

        user = await super().create(db, obj_in=obj_in)

        # Explicitly load the organization after creation
        stmt = select(User).where(User.id == user.id).options(selectinload(User.organization))
        result = await db.execute(stmt)
        return result.scalar_one_or_none() or user

    async def remove(self, db: AsyncSession, *, id: UUID, current_user: User) -> Optional[User]:
        """Remove an object by ID.

        Args:
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to remove. Doesn't require strict typing.
            current_user (User): The current user.

        Returns:
            Optional[User]: The removed user.
        """
        # Now implemented with organization context
        user = await self.get(db, id=id, current_user=current_user)
        if user:
            await db.delete(user)
            await db.commit()
        return user

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: User,
        obj_in: UserUpdate | dict[str, Any],
        current_user: User,
    ) -> User:
        """Update an object.

        Args:
            db (AsyncSession): The database session.
            db_obj (User): The object to update.
            obj_in (UserUpdate | dict[str, Any]): The updated object.
            current_user (User): The current user.

        Returns:
            User: The updated user.
        """
        # Ensure the organization_id is not removed
        if isinstance(obj_in, dict):
            update_data = obj_in
            if "organization_id" in update_data and update_data["organization_id"] is None:
                raise ValueError("User must have an organization")
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
            if "organization_id" in update_data and update_data["organization_id"] is None:
                raise ValueError("User must have an organization")

        updated_user = await super().update(db, db_obj=db_obj, obj_in=update_data)

        # Explicitly load the organization after update
        stmt = (
            select(User).where(User.id == updated_user.id).options(selectinload(User.organization))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none() or updated_user

    async def get_by_api_key(self, db: AsyncSession, *, api_key: str) -> Optional[User]:
        """Get a user by API key."""
        # Hash the provided key to compare against stored SHA256-hashed keys
        from hashlib import sha256

        hashed_key = sha256(api_key.encode()).hexdigest()
        # Join User with APIKey to find the user associated with this hashed key
        stmt = (
            select(User)
            .join(APIKey, User.email == APIKey.created_by_email)
            .where(APIKey.key == hashed_key)
            .options(selectinload(User.organization))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


user = CRUDUser(User)
