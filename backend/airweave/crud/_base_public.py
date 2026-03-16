"""Base CRUD class for system-wide public resources."""

from typing import Any, Generic, Optional, Type, TypeVar, Union
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.exceptions import NotFoundException
from airweave.db.unit_of_work import UnitOfWork
from airweave.models._base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDPublic(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """CRUD for system-wide public resources."""

    def __init__(self, model: Type[ModelType]):
        """Initialize the CRUD object.

        Args:
        ----
            model (Type[ModelType]): The model to be used in the CRUD operations.
        """
        self.model = model

    async def get(self, db: AsyncSession, id: UUID) -> Optional[ModelType]:
        """Get public resource - no access control.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to get.

        Returns:
        -------
            Optional[ModelType]: The object with the given ID.
        """
        result = await db.execute(select(self.model).where(self.model.id == id))
        db_obj = result.unique().scalar_one_or_none()
        if not db_obj:
            raise NotFoundException(f"Object with ID {id} not found")
        return db_obj

    async def get_by_short_name(self, db: AsyncSession, short_name: str) -> Optional[ModelType]:
        """Get public resource by short name.

        Args:
        ----
            db (AsyncSession): The database session.
            short_name (str): The short name of the object to get.

        Returns:
        -------
            Optional[ModelType]: The object with the given short name.
        """
        result = await db.execute(select(self.model).where(self.model.short_name == short_name))
        db_obj = result.unique().scalar_one_or_none()
        if not db_obj:
            raise NotFoundException(f"Object with short name {short_name} not found")
        return db_obj

    async def get_multi(
        self,
        db: AsyncSession,
        organization_id: Optional[UUID] = None,
        *,
        skip: int = 0,
        limit: int = 100,
        disable_limit: bool = True,
    ) -> list[ModelType]:
        """Get public resources, optionally filtered by organization.

        Args:
        ----
            db (AsyncSession): The database session.
            organization_id (Optional[UUID]): The organization ID to filter by.
            skip (int): The number of objects to skip.
            limit (int): The number of objects to return.
            disable_limit (bool): Disable the limit parameter by default.

        Returns:
        -------
            list[ModelType]: A list of objects.
        """
        query = select(self.model)

        # If model has organization_id, filter by it
        if hasattr(self.model, "organization_id") and organization_id:
            query = query.where(
                (self.model.organization_id == organization_id)
                | (self.model.organization_id.is_(None))  # Include system-wide
            )

        query = query.offset(skip)
        if not disable_limit:
            query = query.limit(limit)

        result = await db.execute(query)
        return list(result.unique().scalars().all())

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: CreateSchemaType,
        uow: Optional[UnitOfWork] = None,
    ) -> ModelType:
        """Create public resource.

        Args:
        ----
            db (AsyncSession): The database session.
            obj_in (CreateSchemaType): The object to create.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            ModelType: The created object.
        """
        if not isinstance(obj_in, dict):
            obj_in_data = obj_in.model_dump(exclude_unset=True)
        else:
            obj_in_data = obj_in

        db_obj = self.model(**obj_in_data)
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
        uow: Optional[UnitOfWork] = None,
    ) -> ModelType:
        """Update public resource.

        Args:
        ----
            db (AsyncSession): The database session.
            db_obj (ModelType): The object to update.
            obj_in (Union[UpdateSchemaType, dict[str, Any]]): The new object data.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            ModelType: The updated object.
        """
        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump(exclude_unset=True)

        for field, value in obj_in.items():
            setattr(db_obj, field, value)

        if not uow:
            await db.commit()
            await db.refresh(db_obj)

        return db_obj

    async def remove(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        uow: Optional[UnitOfWork] = None,
    ) -> Optional[ModelType]:
        """Delete public resource.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to delete.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            Optional[ModelType]: The deleted object.
        """
        result = await db.execute(select(self.model).where(self.model.id == id))
        db_obj = result.unique().scalar_one_or_none()

        if db_obj is None:
            raise NotFoundException(f"Object with ID {id} not found")

        await db.delete(db_obj)

        if not uow:
            await db.commit()

        return db_obj

    async def get_all(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100, disable_limit: bool = True
    ) -> list[ModelType]:
        """Get multiple objects.

        Args:
        ----
            db (AsyncSession): The database session.
            skip (int): The number of objects to skip.
            limit (int): The number of objects to return.
            disable_limit (bool): Disable the limit parameter by default.

        Returns:
        -------
            List[ModelType]: A list of objects.

        """
        query = select(self.model).offset(skip)
        if not disable_limit:
            query = query.limit(limit)

        result = await db.execute(query)
        return list(result.unique().scalars().all())

    async def create_many(
        self, db: AsyncSession, objs_in: list[CreateSchemaType], uow: Optional[UnitOfWork] = None
    ) -> list[ModelType]:
        """Create multiple objects.

        Args:
        ----
            db (AsyncSession): The database session.
            objs_in (list[CreateSchemaType]): The objects to create.
            uow (UnitOfWork, optional): Unit of work for transaction control.

        Returns:
        -------
            list[ModelType]: The created objects.

        """
        db_objs = [self.model(**obj_in.model_dump()) for obj_in in objs_in]
        db.add_all(db_objs)

        if uow is None:
            await db.commit()

        return db_objs

    async def sync(
        self, db: AsyncSession, items: list[CreateSchemaType], unique_field: str = "short_name"
    ) -> None:
        """Sync items with the database.

        Args:
        ----
            db (AsyncSession): The database session.
            items (list[CreateSchemaType]): The items to sync.
            unique_field (str): The field to use for uniqueness.
        """
        # Create a dictionary of new items by their unique field
        new_items_dict = {getattr(item, unique_field): item for item in items}

        # Get existing items
        result = await db.execute(select(self.model))
        existing_items = result.scalars().all()

        # Update existing items or delete them
        for existing_item in existing_items:
            existing_unique_value = getattr(existing_item, unique_field)
            if existing_unique_value in new_items_dict:
                new_item = new_items_dict.pop(existing_unique_value)

                # Update fields from new item
                for field, value in new_item.model_dump().items():
                    if hasattr(existing_item, field):
                        setattr(existing_item, field, value)

                db.add(existing_item)
            else:
                await db.delete(existing_item)

        # Create new items
        for new_item in new_items_dict.values():
            db_item = self.model(**new_item.model_dump())
            db.add(db_item)

        await db.commit()
