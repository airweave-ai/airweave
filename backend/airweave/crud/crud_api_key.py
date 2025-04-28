"""CRUD operations for the APIKey model."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.exceptions import NotFoundException
from airweave.crud._base import CRUDBase
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.api_key import APIKey
from airweave.schemas import APIKeyCreate, APIKeyUpdate, User


class CRUDAPIKey(CRUDBase[APIKey, APIKeyCreate, APIKeyUpdate]):
    """CRUD operations for the APIKey model."""

    async def create_with_user(
        self,
        db: AsyncSession,
        *,
        obj_in: APIKeyCreate,
        current_user: User,
        uow: Optional[UnitOfWork] = None,
    ) -> APIKey:
        """Create a new API key for a user.

        Args:
        ----
            db (AsyncSession): The database session.
            obj_in (APIKeyCreate): The API key creation data.
            current_user (User): The current user.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            APIKey: The created API key.

        """
        key = secrets.token_urlsafe(32)
        hashed_key = hashlib.sha256(key.encode()).hexdigest()
        key_prefix = key[:8]

        expiration_date = obj_in.expiration_date or (
            datetime.now(timezone.utc) + timedelta(days=180)  # Default to 180 days
        )

        db_obj = APIKey(
            key=hashed_key,
            key_prefix=key_prefix,
            created_by_email=current_user.email,
            modified_by_email=current_user.email,
            expiration_date=expiration_date,
            # Set the organization_id from the current user
            organization_id=current_user.organization_id,
        )
        db.add(db_obj)
        if not uow:
            await db.commit()
            await db.refresh(db_obj)

        # Attach the plain key to the object for the response, this is not stored in the db
        db_obj.plain_key = key
        return db_obj

    async def get_all_for_user(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100, current_user: User
    ) -> list[APIKey]:
        """Get all API keys for a user.

        Args:
        ----
            db (AsyncSession): The database session.
            skip (int): The number of records to skip.
            limit (int): The maximum number of records to return.
            current_user (User): The current user.

        Returns:
        -------
            list[APIKey]: A list of API keys for the user.

        """
        # Get API keys by organization ID
        query = (
            select(self.model)
            .where(self.model.organization_id == current_user.organization_id)
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get(self, db: AsyncSession, id: UUID, current_user: User) -> Optional[APIKey]:
        """Get an API key by ID.

        Args:
        ----
            db (AsyncSession): The database session.
            id (str): The ID of the API key to get.
            current_user (User): The current user.

        Returns:
        -------
            Optional[APIKey]: The API key if found.

        """
        # Get API key by ID and organization ID
        query = select(self.model).where(
            self.model.id == id, self.model.organization_id == current_user.organization_id
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def remove(self, db: AsyncSession, *, id: UUID, current_user: User) -> None:
        """Remove an API key.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The ID of the API key to remove.
            current_user (User): The current user.

        Returns:
        -------
            None
        """
        # Delete API key by ID and organization ID for security
        stmt = delete(self.model).where(
            self.model.id == id, self.model.organization_id == current_user.organization_id
        )
        await db.execute(stmt)
        await db.commit()

    async def get_by_key(self, db: AsyncSession, *, key: str) -> Optional[APIKey]:
        """Get an API key by its hashed value.

        Args:
        ----
            db (AsyncSession): The database session
            key (str): The plain API key to look up

        Returns:
        -------
            Optional[APIKey]: The API key if found and valid

        Raises:
        ------
            ValueError: If the API key has expired
            NotFoundException: If the API key is not found
        """
        # Hash the provided key for comparison
        hashed_key = hashlib.sha256(key.encode()).hexdigest()

        # Query for the API key
        query = select(self.model).where(self.model.key == hashed_key)
        result = await db.execute(query)
        db_obj = result.unique().scalar_one_or_none()

        if not db_obj:
            raise NotFoundException("API key not found")

        # Check if the key has expired
        if db_obj.expiration_date and db_obj.expiration_date < datetime.now(timezone.utc):
            raise ValueError("API key has expired")

        return db_obj


api_key = CRUDAPIKey(APIKey)
