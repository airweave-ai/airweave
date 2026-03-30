"""Base CRUD class for user-level data."""

from typing import Any, Generic, Optional, Type, TypeVar, Union
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.exceptions import NotFoundException, PermissionException
from airweave.db.unit_of_work import UnitOfWork
from airweave.models._base import Base
from airweave.models.user import User

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBaseUser(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """CRUD for pure user-level data."""

    def __init__(self, model: Type[ModelType]):
        """Initialize the CRUD object.

        Args:
        ----
            model (Type[ModelType]): The model to be used in the CRUD operations.
        """
        self.model = model

    async def get(self, db: AsyncSession, id: UUID, current_user: User) -> ModelType:
        """Get user data - must be same user.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to get.
            current_user (User): The current user.

        Returns:
        -------
            ModelType: The object with the given ID.

        Raises:
        ------
            PermissionException: If user tries to access another user's data.
            NotFoundException: If the object does not exist.
        """
        if id != current_user.id:
            raise PermissionException("Cannot access other user's data")

        result = await db.execute(select(self.model).where(self.model.id == id))
        db_obj = result.unique().scalar_one_or_none()
        if not db_obj:
            raise NotFoundException(f"{self.model.__name__} not found")
        return db_obj

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: CreateSchemaType,
        current_user: User,
        uow: Optional[UnitOfWork] = None,
    ) -> ModelType:
        """Create user data.

        Args:
        ----
            db (AsyncSession): The database session.
            obj_in (CreateSchemaType): The object to create.
            current_user (User): The current user.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            ModelType: The created object.
        """
        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump(exclude_unset=True)

        # Ensure the object belongs to the current user
        obj_in["id"] = current_user.id

        db_obj = self.model(**obj_in)
        db.add(db_obj)

        if not uow:
            await db.commit()
            await db.refresh(db_obj)

        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, dict[str, Any]],
        current_user: User,
        uow: Optional[UnitOfWork] = None,
    ) -> ModelType:
        """Update user data.

        Args:
        ----
            db (AsyncSession): The database session.
            db_obj (ModelType): The object to update.
            obj_in (Union[UpdateSchemaType, dict[str, Any]]): The new object data.
            current_user (User): The current user.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            ModelType: The updated object.
        """
        if db_obj.id != current_user.id:
            raise PermissionException("Cannot update other user's data")

        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump(exclude_unset=True)

        for field, value in obj_in.items():
            setattr(db_obj, field, value)

        if not uow:
            await db.commit()
            await db.refresh(db_obj)

        return db_obj

    async def remove(self, db: AsyncSession, id: UUID, current_user: User) -> ModelType:
        """Remove user data.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to remove.
            current_user (User): The current user.

        Returns:
        -------
            ModelType: The deleted object.

        Raises:
        ------
            PermissionException: If user tries to remove another user's data.
            NotFoundException: If the object does not exist.
        """
        if id != current_user.id:
            raise PermissionException("Cannot remove other user's data")

        result = await db.execute(select(self.model).where(self.model.id == id))
        db_obj = result.unique().scalar_one_or_none()
        if not db_obj:
            raise NotFoundException(f"{self.model.__name__} not found")
        await db.delete(db_obj)
        return db_obj
