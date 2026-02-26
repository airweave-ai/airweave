"""CRUD operations for the APIKey model."""

import secrets
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core import credentials
from airweave.core.context import BaseContext
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.exceptions import NotFoundException, PermissionException
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.api_key import APIKey
from airweave.schemas import APIKeyCreate, APIKeyUpdate


class CRUDAPIKey(CRUDBaseOrganization[APIKey, APIKeyCreate, APIKeyUpdate]):
    """CRUD operations for the APIKey model."""

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: APIKeyCreate,
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> APIKey:
        """Create a new API key with auth context.

        Args:
        ----
            db (AsyncSession): The database session.
            obj_in (APIKeyCreate): The API key creation data.
            ctx (BaseContext): The API context.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            APIKey: The created API key.
        """
        key = secrets.token_urlsafe(32)
        encrypted_key = credentials.encrypt({"key": key})

        # Calculate expiration date from days (defaults to 90)
        expiration_days = obj_in.expiration_days if obj_in.expiration_days is not None else 90
        expiration_date = utc_now_naive() + timedelta(days=expiration_days)

        # Create a dictionary with the data instead of using the schema
        api_key_data = {
            "encrypted_key": encrypted_key,
            "expiration_date": expiration_date,
        }

        # Use the parent create method which handles organization scoping and user tracking
        return await super().create(
            db=db,
            obj_in=api_key_data,
            ctx=ctx,
            uow=uow,
            skip_validation=True,
        )

    async def get_all_for_ctx(
        self,
        db: AsyncSession,
        ctx: BaseContext,
        organization_id: Optional[UUID] = None,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[APIKey]:
        """Get all API keys for an API context's organization.

        Args:
        ----
            db (AsyncSession): The database session.
            ctx (BaseContext): The API context.
            organization_id (Optional[UUID]): The organization ID to filter by.
            skip (int): The number of records to skip.
            limit (int): The maximum number of records to return.

        Returns:
        -------
            list[APIKey]: A list of API keys for the organization.
        """
        # Use the parent method which handles organization scoping and access validation
        return await self.get_multi(
            db=db,
            ctx=ctx,
            organization_id=organization_id,
            skip=skip,
            limit=limit,
        )

    async def get_by_key(self, db: AsyncSession, *, key: str) -> Optional[APIKey]:
        """Get an API key by validating the provided plain key against all stored encrypted keys.

        This method decrypts each stored API key and compares it with the provided key.
        If a match is found and the key hasn't expired, returns the API key object.

        Args:
        ----
            db (AsyncSession): The database session.
            key (str): The plain API key to validate.

        Returns:
        -------
            Optional[APIKey]: The API key if found and valid.

        Raises:
        ------
            NotFoundException: If no matching API key is found.
            ValueError: If the matching API key has expired.

        Note:
        ----
            This method needs to decrypt each stored key for comparison since
            Fernet encryption is non-deterministic (same input produces different
            encrypted outputs). This is less efficient than hash-based lookups
            but necessary for symmetric encryption.
        """
        # Query all API keys (we need to check each one)
        # Note: This method doesn't require organization scoping since it's used for authentication
        query = select(self.model)
        result = await db.execute(query)
        api_keys = result.scalars().all()

        # Check each key
        for api_key in api_keys:
            try:
                decrypted_data = credentials.decrypt(api_key.encrypted_key)
                if decrypted_data["key"] == key:
                    # Check expiration
                    if api_key.expiration_date < utc_now_naive():
                        raise PermissionException("API key has expired")
                    return api_key
            except Exception:
                continue

        raise NotFoundException("API key not found")

    async def get_keys_expiring_in_range(
        self,
        db: AsyncSession,
        start_date: datetime,
        end_date: datetime,
    ) -> list[APIKey]:
        """Get API keys expiring within a date range.

        Args:
        ----
            db (AsyncSession): The database session.
            start_date (datetime): Start of the date range (inclusive).
            end_date (datetime): End of the date range (exclusive).

        Returns:
        -------
            list[APIKey]: List of API keys expiring in the range.

        """
        from sqlalchemy import and_, select

        query = select(self.model).where(
            and_(
                self.model.expiration_date >= start_date,
                self.model.expiration_date < end_date,
            )
        )

        result = await db.execute(query)
        return list(result.scalars().all())


api_key = CRUDAPIKey(APIKey)
