"""CRUD operations for connections."""

from typing import Any, Optional, Union
from uuid import UUID

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from airweave.core.context import BaseContext
from airweave.core.exceptions import NotFoundException, PermissionException
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.connection import Connection, IntegrationType
from airweave.schemas.connection import ConnectionCreate, ConnectionUpdate


class CRUDConnection(CRUDBaseOrganization[Connection, ConnectionCreate, ConnectionUpdate]):
    """CRUD operations for connections."""

    # Native connection short names
    NATIVE_CONNECTION_SHORT_NAMES = [
        "qdrant_native",
        "neo4j_native",
        "vespa_native",
        "local_text2vec",
    ]

    def _is_native_connection(self, connection: Connection) -> bool:
        """Check if a connection is a native system-level connection.

        Native connections have specific short names and no organization_id, created_by_email,
        or modified_by_email.

        Args:
        ----
            connection (Connection): The connection to check.

        Returns:
        -------
            bool: True if the connection is a native connection, False otherwise.
        """
        return (
            connection.short_name in self.NATIVE_CONNECTION_SHORT_NAMES
            and connection.organization_id is None
            and connection.created_by_email is None
            and connection.modified_by_email is None
        )

    async def get(self, db: AsyncSession, id: UUID, ctx: BaseContext) -> Optional[Connection]:
        """Get a single connection by ID, with special handling for native connections.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The UUID of the connection to get.
            ctx (BaseContext): The current authentication context.

        Returns:
        -------
            Optional[Connection]: The connection with the given ID.

        """
        query = select(self.model).where(self.model.id == id)
        result = await db.execute(query)
        db_obj = result.unique().scalar_one_or_none()

        if not db_obj:
            raise NotFoundException(f"Connection with ID {id} not found")

        # If it's not a native connection, validate user permissions
        if not self._is_native_connection(db_obj):
            await self._validate_organization_access(ctx, db_obj.organization_id)

        return db_obj

    async def get_multi(
        self, db: AsyncSession, ctx: BaseContext, *, skip: int = 0, limit: int = 100
    ) -> list[Connection]:
        """Get all connections for a user, including native connections.

        This combines user-specific connections with system-level native connections.

        Args:
        ----
            db (AsyncSession): The database session.
            ctx (BaseContext): The current authentication context.
            skip (int): The number of objects to skip.
            limit (int): The number of objects to return.

        Returns:
        -------
            list[Connection]: A list of connections, including native ones.

        """
        # Get user connections
        user_query = (
            select(self.model)
            .where(
                self.model.organization_id == ctx.organization.id,
            )
            .order_by(desc(self.model.created_at))
            .offset(skip)
            .limit(limit)
        )
        user_result = await db.execute(user_query)
        user_connections = list(user_result.unique().scalars().all())

        # Get native connections
        native_query = select(self.model).where(
            self.model.organization_id.is_(None),
            or_(
                *[
                    self.model.short_name == short_name
                    for short_name in self.NATIVE_CONNECTION_SHORT_NAMES
                ]
            ),
        )
        native_result = await db.execute(native_query)
        native_connections = list(native_result.unique().scalars().all())

        # Combine and return all connections
        return user_connections + native_connections

    async def get_by_integration_type(
        self, db: AsyncSession, integration_type: IntegrationType, ctx: BaseContext
    ) -> list[Connection]:
        """Get all active connections for a specific integration type, including native connections.

        This combines organization-specific connections with the system-level native connections.
        Native connections are included if they match the integration type.

        Args:
            db: The database session
            integration_type: The integration type to filter by
            ctx: The current authentication context

        Returns:
            A list of Connection objects including both organization connections and native ones
        """
        # Query for org-specific connections
        org_query = (
            select(Connection)
            .options(selectinload(Connection.integration_credential))
            .where(
                Connection.integration_type == integration_type,
                Connection.organization_id == ctx.organization.id,
            )
        )
        org_result = await db.execute(org_query)
        org_connections = list(org_result.scalars().all())

        # Query for native connections of the same integration type
        native_query = (
            select(Connection)
            .options(selectinload(Connection.integration_credential))
            .where(
                Connection.integration_type == integration_type,
                Connection.organization_id.is_(None),
                or_(
                    *[
                        Connection.short_name == short_name
                        for short_name in self.NATIVE_CONNECTION_SHORT_NAMES
                    ]
                ),
            )
        )
        native_result = await db.execute(native_query)
        native_connections = list(native_result.scalars().all())

        # Combine the results
        return org_connections + native_connections

    async def get_all_by_short_name(
        self, db: AsyncSession, short_name: str, ctx: BaseContext
    ) -> list[Connection]:
        """Get all connections for a specific short name, with proper organization filtering.

        This combines organization-specific connections with system-level native connections.
        Native connections are included if they match the short name.

        Args:
            db: The database session
            short_name: The short name to filter by
            ctx: The current authentication context

        Returns:
            A list of Connection objects including both organization connections and native ones
        """
        # Query for org-specific connections
        org_query = (
            select(Connection)
            .options(selectinload(Connection.integration_credential))
            .where(
                Connection.short_name == short_name,
                Connection.organization_id == ctx.organization.id,
            )
        )
        org_result = await db.execute(org_query)
        org_connections = list(org_result.scalars().all())

        # Query for native connections with the same short name
        native_query = (
            select(Connection)
            .options(selectinload(Connection.integration_credential))
            .where(
                Connection.short_name == short_name,
                Connection.organization_id.is_(None),
                or_(
                    *[
                        Connection.short_name == native_short_name
                        for native_short_name in self.NATIVE_CONNECTION_SHORT_NAMES
                    ]
                ),
            )
        )
        native_result = await db.execute(native_query)
        native_connections = list(native_result.scalars().all())

        # Combine the results
        return org_connections + native_connections

    async def get_by_readable_id(
        self, db: AsyncSession, readable_id: str, ctx: BaseContext
    ) -> Optional[Connection]:
        """Get a connection by its readable_id, with special handling for native connections.

        Args:
            db: The database session
            readable_id: The readable_id of the connection to get
            ctx: The current authentication context

        Returns:
            The connection with the given readable_id

        Raises:
            NotFoundException: If the connection is not found
            PermissionException: If the user doesn't have access to the connection
        """
        query = select(self.model).where(self.model.readable_id == readable_id)
        result = await db.execute(query)
        db_obj = result.unique().scalar_one_or_none()

        if not db_obj:
            return None

        # If it's not a native connection, validate user permissions
        if not self._is_native_connection(db_obj):
            await self._validate_organization_access(ctx, db_obj.organization_id)

        return db_obj

    async def remove(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Optional[Connection]:
        """Delete a connection, with special handling for native connections.

        Native connections cannot be deleted as they are system-level resources.

        Args:
        ----
            db (AsyncSession): The database session.
            id (UUID): The UUID of the connection to delete.
            ctx (BaseContext): The current authentication context.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            Optional[Connection]: The deleted connection.

        Raises:
        ------
            PermissionException: If attempting to delete a native connection or if the user
                does not have permission to delete the connection.
        """
        query = select(self.model).where(self.model.id == id)
        result = await db.execute(query)
        db_obj = result.unique().scalar_one_or_none()

        if not db_obj:
            raise NotFoundException(f"Connection with ID {id} not found")

        # Prevent deletion of native connections
        if self._is_native_connection(db_obj):
            raise PermissionException(
                "Native connections cannot be deleted as they are system-level resources"
            )

        # For regular connections, validate user permissions
        await self._validate_organization_access(ctx, db_obj.organization_id)

        await db.delete(db_obj)

        if not uow:
            await db.commit()

        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: Connection,
        obj_in: Union[ConnectionUpdate, dict[str, Any]],
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> Connection:
        """Update a connection, with special handling for native connections.

        Native connections cannot be updated as they are system-level resources.

        Args:
        ----
            db (AsyncSession): The database session.
            db_obj (Connection): The connection to update.
            obj_in (Union[ConnectionUpdate, dict[str, Any]]): The new connection data.
            ctx (BaseContext): The current authentication context.
            uow (Optional[UnitOfWork]): The unit of work to use for the transaction.

        Returns:
        -------
            Connection: The updated connection.

        Raises:
        ------
            PermissionException: If attempting to update a native connection or if the user
                does not have permission to update the connection.
        """
        # Prevent updates to native connections
        if self._is_native_connection(db_obj):
            raise PermissionException(
                "Native connections cannot be updated as they are system-level resources"
            )

        # For regular connections, proceed with the normal update
        return await super().update(db=db, db_obj=db_obj, obj_in=obj_in, ctx=ctx, uow=uow)


connection = CRUDConnection(Connection)
