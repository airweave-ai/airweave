"""Unified CRUD class for organization-scoped resources."""

from typing import Any, Generic, Optional, Type, TypeVar, Union
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.context import BaseContext
from airweave.core.exceptions import NotFoundException, PermissionException
from airweave.db.unit_of_work import UnitOfWork
from airweave.models._base import Base

ModelType = TypeVar("ModelType", bound=Base)

CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBaseOrganization(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Unified CRUD for all organization-scoped resources."""

    def __init__(self, model: Type[ModelType], track_user: bool = True):
        """Initialize the CRUD object.

        Args:
        ----
            model (Type[ModelType]): The model to be used in the CRUD operations.
            track_user (bool): Whether model has UserMixin (created_by_email, modified_by_email).
        """
        self.model = model
        self.track_user = track_user

    async def get(
        self,
        db: AsyncSession,
        id: UUID,
        ctx: BaseContext,
    ) -> Optional[ModelType]:
        """Get organization resource.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to get.
            ctx (BaseContext): The API context.

        Returns:
        -------
            Optional[ModelType]: The object with the given ID.
        """
        # Validate auth context has org access

        query = select(self.model).where(
            self.model.id == id, self.model.organization_id == ctx.organization.id
        )

        result = await db.execute(query)
        db_obj = result.unique().scalar_one_or_none()
        if db_obj is None:
            raise NotFoundException(f"{self.model.__name__} not found")

        await self._validate_organization_access(ctx, db_obj.organization_id)

        return db_obj

    async def get_multi(
        self,
        db: AsyncSession,
        ctx: BaseContext,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ModelType]:
        """Get all resources for organization.

        Args:
        ----
            db (AsyncSession): The database session.
            ctx (BaseContext): The API context.
            skip (int): The number of objects to skip.
            limit (int): The number of objects to return.

        Returns:
        -------
            list[ModelType]: A list of objects.
        """
        # Validate auth context has org access

        query = (
            select(self.model)
            .where(self.model.organization_id == ctx.organization.id)
            .offset(skip)
            .limit(limit)
        )

        result = await db.execute(query)
        db_objs = result.unique().scalars().all()

        for db_obj in db_objs:
            await self._validate_organization_access(ctx, db_obj.organization_id)

        return db_objs

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: CreateSchemaType,
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
        skip_validation: bool = False,
    ) -> ModelType:
        """Create organization resource with auth context.

        Args:
        ----
            db (AsyncSession): The database session.
            obj_in (CreateSchemaType): The object to create.
            ctx (BaseContext): The API context.
            organization_id (Optional[UUID]): The organization ID to create in.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.
            skip_validation (bool): Whether to skip validation.

        Returns:
        -------
            ModelType: The created object.
        """
        if not skip_validation:
            # Validate auth context has org access
            await self._validate_organization_access(ctx, ctx.organization.id)

        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump(exclude_unset=True)

        obj_in["organization_id"] = ctx.organization.id

        if self.track_user:
            if ctx.has_user_context:
                # Human user: track directly
                obj_in["created_by_email"] = ctx.tracking_email
                obj_in["modified_by_email"] = ctx.tracking_email
            else:
                # API key/system: nullable tracking
                obj_in["created_by_email"] = None
                obj_in["modified_by_email"] = None

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
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> ModelType:
        """Update organization resource with auth context.

        Args:
        ----
            db (AsyncSession): The database session.
            db_obj (ModelType): The object to update.
            obj_in (Union[UpdateSchemaType, dict[str, Any]]): The new object data.
            ctx (BaseContext): The API context.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            ModelType: The updated object.
        """
        # Validate auth context has org access
        await self._validate_organization_access(ctx, db_obj.organization_id)

        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump(exclude_unset=True)

        if self.track_user and ctx.has_user_context:
            obj_in["modified_by_email"] = ctx.tracking_email

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
        ctx: BaseContext,
        organization_id: Optional[UUID] = None,
        uow: Optional[UnitOfWork] = None,
    ) -> Optional[ModelType]:
        """Delete organization resource with auth context.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The UUID of the object to delete.
            ctx (BaseContext): The API context.
            organization_id (Optional[UUID]): The organization ID to delete from.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            Optional[ModelType]: The deleted object.
        """
        effective_org_id = organization_id or ctx.organization.id

        query = select(self.model).where(
            self.model.id == id, self.model.organization_id == effective_org_id
        )
        result = await db.execute(query)
        db_obj = result.unique().scalar_one_or_none()

        if db_obj is None:
            raise NotFoundException(f"{self.model.__name__} not found")

        # Validate auth context has org access
        await self._validate_organization_access(ctx, db_obj.organization_id)

        await db.delete(db_obj)

        if not uow:
            await db.commit()

        return db_obj

    async def get_by_query_and_org(
        self, db: AsyncSession, *, ctx: BaseContext, **kwargs: Any
    ) -> Optional[ModelType]:
        """Get a single object by a flexible query, scoped to the organization.

        Args:
            db: The database session.
            ctx: The API context.
            **kwargs: The query parameters (e.g., name="test", id=UUID(...)).

        Returns:
            The object if found, otherwise None.
        """
        query = select(self.model).where(self.model.organization_id == ctx.organization.id)
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)
            else:
                # Defensive: prevent querying on columns that don't exist
                raise AttributeError(f"Model {self.model.__name__} has no attribute '{key}'")

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def bulk_remove(
        self,
        db: AsyncSession,
        *,
        ids: list[UUID],
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> list[ModelType]:
        """Delete organization resources with auth context.

        Args:
        ----
            db (AsyncSession): The database session.
            ids (list[UUID]): The UUIDs of the objects to delete.
            ctx (BaseContext): The API context.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            list[ModelType]: The deleted objects.
        """
        query = select(self.model).where(
            self.model.id.in_(ids), self.model.organization_id == ctx.organization.id
        )
        result = await db.execute(query)
        db_objs = result.unique().scalars().all()

        # Validate access for all objects
        for db_obj in db_objs:
            await self._validate_organization_access(ctx, db_obj.organization_id)

        # Delete each object individually
        for db_obj in db_objs:
            await db.delete(db_obj)

        if not uow:
            await db.commit()

        return db_objs

    async def _validate_organization_access(self, ctx: BaseContext, organization_id: UUID) -> None:
        """Validate auth context has access to organization.

        Args:
        ----
            ctx (BaseContext): The API context.
            organization_id (UUID): The organization ID to validate access to.

        Raises:
        ------
            PermissionException: If auth context does not have access to organization.
        """
        if ctx.has_user_context:
            # Admin users bypass organization access validation
            if ctx.user.is_admin:
                return

            if organization_id not in [org.organization.id for org in ctx.user.user_organizations]:
                raise PermissionException("User does not have access to organization")
        else:
            if organization_id != ctx.organization.id:
                raise PermissionException("API key does not have access to organization")
