"""CRUD operations for syncs."""

from typing import Any, Optional, Union
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, models, schemas
from airweave.core.context import BaseContext
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.exceptions import NotFoundException
from airweave.core.shared_models import IntegrationType, SyncStatus
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.connection import Connection
from airweave.models.sync import Sync
from airweave.models.sync_connection import SyncConnection
from airweave.schemas.sync import SyncCreate, SyncUpdate


class CRUDSync(CRUDBaseOrganization[Sync, SyncCreate, SyncUpdate]):
    """CRUD operations for syncs."""

    async def get(
        self,
        db: AsyncSession,
        id: UUID,
        ctx: BaseContext,
        with_connections: bool = True,
    ) -> models.Sync | schemas.Sync:
        """Get the sync by ID.

        If with_connections is True, the sync will be enriched with all its connections,
        and returned as a schemas.Sync object.

        If with_connections is False, the sync will not be enriched with any connections,
        and returned as a models.Sync object.

        Args:
            db (AsyncSession): The database session
            id (UUID): The ID of the sync
            ctx (BaseContext): The API context
            with_connections (bool): Whether to include connections in the sync
        Returns:
            models.Sync: The sync without any connections
        """
        # Get the sync without any connections
        sync = await super().get(db, id=id, ctx=ctx)

        if not sync:
            raise NotFoundException("Sync not found")

        if with_connections:
            # Enrich the sync with all its connections
            sync = await self.enrich_sync_with_connections(db, sync=sync)

        # Validate user permissions
        await self._validate_organization_access(ctx, sync.organization_id)
        return sync

    async def get_multi(
        self,
        db: AsyncSession,
        ctx: BaseContext,
        *,
        skip: int = 0,
        limit: int = 100,
        with_connections: bool = True,
    ) -> list[schemas.Sync]:
        """Get all syncs for a user.

        Args:
        ----
            db (AsyncSession): The database session
            ctx (BaseContext): The API context
            skip (int): The number of syncs to skip
            limit (int): The number of syncs to return
            with_connections (bool): Whether to include connections in the syncs

        Returns:
        -------
            list[schemas.Sync]: The syncs
        """
        # Get all syncs for the user using the base class method
        syncs = await super().get_multi(db, ctx, skip=skip, limit=limit)

        # Enrich the syncs with their connections if requested
        if with_connections:
            syncs = [await self.enrich_sync_with_connections(db, sync) for sync in syncs]
        return syncs

    async def enrich_sync_with_connections(
        self, db: AsyncSession, sync: models.Sync
    ) -> schemas.Sync:
        """Enrich a sync with all its connections.

        Args:
            db (AsyncSession): The database session
            sync (models.Sync): The sync

        Returns:
            schemas.Sync: The sync with its connections
        """
        # Simply use the enricher_for_all method with a single sync
        enriched_syncs = await self.enricher_for_all(db, [sync])

        # Return the first (and only) result
        return enriched_syncs[0] if enriched_syncs else None

    async def enricher_for_all(
        self, db: AsyncSession, syncs: list[models.Sync]
    ) -> list[schemas.Sync]:
        """Efficiently enrich multiple syncs with their connections in a single query.

        This method retrieves all connections for all syncs in a single database query,
        making it much more efficient than processing each sync individually.

        Args:
            db (AsyncSession): The database session
            syncs (list[models.Sync]): The list of syncs to enrich

        Returns:
            list[schemas.Sync]: The list of enriched syncs
        """
        if not syncs:
            return []

        # Get all sync IDs
        sync_ids = [sync.id for sync in syncs]

        # Run a single query to get all connections for all syncs
        stmt = (
            select(Connection, SyncConnection)
            .join(SyncConnection, Connection.id == SyncConnection.connection_id)
            .where(SyncConnection.sync_id.in_(sync_ids))
        )
        result = await db.execute(stmt)
        all_connections = result.unique().all()

        # Create a mapping of sync_id to its connections
        sync_connections = {}
        for connection, sync_connection in all_connections:
            sync_id = sync_connection.sync_id
            if sync_id not in sync_connections:
                sync_connections[sync_id] = {
                    "source": None,
                    "destinations": [],
                    "embedding_model": None,  # Deprecated but kept for schema compatibility
                }

            # Categorize the connection based on its type
            if connection.integration_type == IntegrationType.SOURCE:
                sync_connections[sync_id]["source"] = schemas.Connection.model_validate(connection)
            elif connection.integration_type == IntegrationType.DESTINATION:
                sync_connections[sync_id]["destinations"].append(
                    schemas.Connection.model_validate(connection)
                )
            # Note: EMBEDDING_MODEL integration type removed - embeddings now handled by
            # DenseEmbedder and SparseEmbedder singletons, not via connections

        # Create enriched sync objects
        enriched_syncs = []
        for sync in syncs:
            # Prepare the data dictionary with all fields
            sync_dict = {**sync.__dict__}
            if "_sa_instance_state" in sync_dict:
                sync_dict.pop("_sa_instance_state")

            # Get connections for this sync
            connections = sync_connections.get(
                sync.id, {"source": None, "destinations": [], "embedding_model": None}
            )

            # Add connection IDs
            source = connections["source"]
            sync_dict["source_connection_id"] = source.id if source else None

            destinations = connections["destinations"]
            sync_dict["destination_connection_ids"] = [dest.id for dest in destinations]

            # Create the enriched sync
            enriched_syncs.append(schemas.Sync.model_validate(sync_dict))

        return enriched_syncs

    async def get_all(self, db: AsyncSession) -> list[schemas.Sync]:
        """Get all syncs.

        Args:
            db (AsyncSession): The database session

        Returns:
            list[Sync | schemas.Sync]: The syncs, enriched if ctx is provided
        """
        stmt = select(Sync)
        result = await db.execute(stmt)
        syncs = result.scalars().unique().all()

        # Enrich syncs if ctx is provided
        return await self.enricher_for_all(db, syncs)

    async def get_all_with_schedule(self, db: AsyncSession) -> list[schemas.SyncWithoutConnections]:
        """Get all syncs with a schedule that are due to run.

        Returns:
            list[schemas.SyncWithoutConnections]: The syncs without connections
        """
        now = utc_now_naive()
        stmt = select(Sync).where(
            (Sync.status == SyncStatus.ACTIVE)
            & (Sync.cron_schedule.is_not(None))
            & ((Sync.next_scheduled_run <= now) | (Sync.next_scheduled_run.is_(None)))
        )
        result = await db.execute(stmt)
        syncs = result.scalars().unique().all()

        return [schemas.SyncWithoutConnections.model_validate(sync) for sync in syncs]

    async def get_all_for_source_connection(
        self, db: AsyncSession, source_connection_id: UUID, ctx: BaseContext
    ) -> list[schemas.Sync]:
        """Get all syncs for a source connection.

        Args:
            db (AsyncSession): The database session
            source_connection_id (UUID): The ID of the source connection
            ctx (BaseContext): The API context
        Returns:
            list[schemas.Sync]: The enriched syncs
        """
        # Use the SyncConnection join table to find syncs with the given source connection
        stmt = (
            select(Sync)
            .join(SyncConnection, Sync.id == SyncConnection.sync_id)
            .join(Connection, SyncConnection.connection_id == Connection.id)
            .where(SyncConnection.connection_id == source_connection_id)
            .where(Connection.integration_type == IntegrationType.SOURCE)
            .where(Sync.organization_id == ctx.organization.id)
        )
        result = await db.execute(stmt)
        syncs = result.scalars().unique().all()

        # Validate permissions for each sync
        for sync in syncs:
            await self._validate_organization_access(ctx, sync.organization_id)

        # Enrich all syncs in a single efficient query
        return await self.enricher_for_all(db, syncs)

    async def get_all_for_destination_connection(
        self, db: AsyncSession, destination_connection_id: UUID, ctx: BaseContext
    ) -> list[schemas.Sync]:
        """Get all syncs for a destination connection.

        Args:
            db (AsyncSession): The database session
            destination_connection_id (UUID): The ID of the destination connection
            ctx (BaseContext): The API context

        Returns:
            list[schemas.Sync]: The enriched syncs
        """
        # Use the SyncConnection join table to find syncs with the given destination connection
        stmt = (
            select(Sync)
            .join(SyncConnection, Sync.id == SyncConnection.sync_id)
            .join(Connection, SyncConnection.connection_id == Connection.id)
            .where(SyncConnection.connection_id == destination_connection_id)
            .where(Connection.integration_type == IntegrationType.DESTINATION)
            .where(Sync.organization_id == ctx.organization.id)
        )
        result = await db.execute(stmt)
        syncs = result.scalars().unique().all()

        # Validate permissions for each sync
        for sync in syncs:
            await self._validate_organization_access(ctx, sync.organization_id)

        # Enrich all syncs in a single efficient query
        return await self.enricher_for_all(db, syncs)

    async def get_all_syncs_join_with_source_connection(
        self, db: AsyncSession, ctx: BaseContext
    ) -> list[schemas.SyncWithSourceConnection]:
        """Get all syncs join with source connection.

        Args:
            db (AsyncSession): The database session
            ctx (BaseContext): The API context

        Returns:
            list[schemas.SyncWithSourceConnection]: The syncs with their source connections
        """
        # First, get all syncs for the user
        syncs = await super().get_multi(db, ctx)

        # Enrich all syncs efficiently
        enriched_syncs = await self.enricher_for_all(db, syncs)

        # Get all source connections for these syncs using the SyncConnection join table
        stmt = (
            select(Sync, Connection, SyncConnection)
            .join(SyncConnection, Sync.id == SyncConnection.sync_id)
            .join(Connection, SyncConnection.connection_id == Connection.id)
            .where(Sync.organization_id == ctx.organization.id)
            .where(Connection.integration_type == IntegrationType.SOURCE)
        )
        result = await db.execute(stmt)
        rows = result.unique().all()

        # Create a mapping of sync_id to source connection
        sync_to_source_connection = {
            sync.id: schemas.Connection.model_validate(connection) for sync, connection, _ in rows
        }

        # Create SyncWithSourceConnection objects
        result_syncs = []
        for sync in enriched_syncs:
            if sync.id in sync_to_source_connection:
                sync_with_source = schemas.SyncWithSourceConnection(
                    **sync.model_dump(),
                    source_connection=sync_to_source_connection[sync.id],
                )
                result_syncs.append(sync_with_source)

        return result_syncs

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: SyncCreate,
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> schemas.Sync:
        """Create a sync.

        1. Pop off all the connection ids from the obj_in
        2. Then validate the connections
        3. Write sync object to db
        4. Write sync_connection objects to db
        5. Commit and refresh

        Args:
            db (AsyncSession): The database session
            obj_in (SyncCreate): The sync to create
            ctx (BaseContext): The API context
            uow (UnitOfWork, optional): The unit of work
        Returns:
            schemas.Sync: The model validated schema of the created sync
        """
        # Dump the obj_in to a dict
        obj_in_dict = obj_in.model_dump()
        obj_in_dict.pop("run_immediately")

        # Pop off the connection ids
        source_connection_id = obj_in_dict.pop("source_connection_id")
        destination_connection_ids = obj_in_dict.pop("destination_connection_ids")  # this is a list

        # Validate the connections
        await self._validate_connections(
            db,
            source_connection_id,
            destination_connection_ids,
            ctx,
        )

        # Write the sync object to db
        sync = await super().create(db, obj_in=obj_in_dict, ctx=ctx, uow=uow)

        # Flush the session to ensure sync.id is available
        if uow:
            await uow.session.flush()
        else:
            await db.flush()

        # Write the sync_connection objects to db (source + destinations only)
        connection_ids = [source_connection_id] + destination_connection_ids
        for connection_id in connection_ids:
            sync_connection = SyncConnection(
                sync_id=sync.id,
                connection_id=connection_id,
            )
            db.add(sync_connection)

        # Commit and refresh
        if not uow:
            await db.commit()
            await db.refresh(sync)

        # Re-add the connection IDs to create a fully model-validated schema
        sync_dict = {**sync.__dict__}
        if "_sa_instance_state" in sync_dict:
            sync_dict.pop("_sa_instance_state")

        sync_dict["source_connection_id"] = source_connection_id
        sync_dict["destination_connection_ids"] = destination_connection_ids

        # Return a properly model-validated instance
        return schemas.Sync.model_validate(sync_dict)

    async def remove_all_for_connection(
        self, db: AsyncSession, connection_id: UUID, ctx: BaseContext, uow: UnitOfWork
    ) -> list[Sync]:
        """Remove all syncs for a connection.

        Args:
            db (AsyncSession): The database session
            connection_id (UUID): The ID of the connection
            ctx (BaseContext): The API context
            uow (UnitOfWork): The unit of work
        Returns:
            list[Sync]: The removed syncs
        """
        # Use the SyncConnection join table to find all syncs associated with this connection
        stmt = (
            select(Sync)
            .join(SyncConnection, Sync.id == SyncConnection.sync_id)
            .where(SyncConnection.connection_id == connection_id)
            .where(Sync.organization_id == ctx.organization.id)
        )
        result = await db.execute(stmt)
        syncs = result.scalars().unique().all()

        removed_syncs = []
        for sync in syncs:
            removed_sync = await self.remove(db, id=sync.id, ctx=ctx, uow=uow)
            removed_syncs.append(removed_sync)

        return removed_syncs

    async def _validate_connections(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        destination_connection_ids: list[UUID],
        ctx: BaseContext,
    ) -> None:
        """Validate the connections.

        Args:
            db (AsyncSession): The database session
            source_connection_id (UUID): The ID of the source connection
            destination_connection_ids (list[UUID]): The IDs of the destination connections
            ctx (BaseContext): The API context
        """
        # Validate the source connection and that it is a source
        source_connection = await crud.connection.get(db, id=source_connection_id, ctx=ctx)
        if not source_connection:
            raise NotFoundException("Source connection not found")
        if source_connection.integration_type != IntegrationType.SOURCE:
            raise ValueError("Source connection is not a source")

        # Validate the destination connections and that they are destinations
        for destination_connection_id in destination_connection_ids:
            destination_connection = await crud.connection.get(
                db, id=destination_connection_id, ctx=ctx
            )
            if not destination_connection:
                raise NotFoundException("Destination connection not found")

            if destination_connection.integration_type != IntegrationType.DESTINATION:
                raise ValueError("Destination connection is not a destination")

        # Note: embedding_model_connection_id validation removed
        # Embeddings are now handled by DenseEmbedder and SparseEmbedder singletons
        # The field is kept in the schema for backwards compatibility but is not validated

    async def remove(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> schemas.Sync:
        """Remove a sync.

        Override the base method to ensure the returned sync is enriched with connections.

        Args:
            db (AsyncSession): The database session
            id (UUID): The ID of the sync
            ctx (BaseContext): The API context
            uow (UnitOfWork, optional): The unit of work

        Returns:
            schemas.Sync: The model validated schema of the removed sync
        """
        # First, fetch the sync with its connections before deletion
        enriched_sync = await self.get(db, id=id, ctx=ctx)

        # Delete the sync_connection records first to avoid foreign key constraint violations
        delete_stmt = delete(SyncConnection).where(SyncConnection.sync_id == id)
        await db.execute(delete_stmt)

        # Flush the changes to make sure they're applied before deleting the sync
        await db.flush()

        # Then remove using the base method
        removed_sync = await super().remove(db, id=id, ctx=ctx, uow=uow)

        # The connections are already deleted, so we need to create the response
        # from the previously enriched sync
        sync_dict = {**removed_sync.__dict__}
        if "_sa_instance_state" in sync_dict:
            sync_dict.pop("_sa_instance_state")

        # Add the connection IDs from the pre-fetched enriched sync
        sync_dict["source_connection_id"] = enriched_sync.source_connection_id
        sync_dict["destination_connection_ids"] = enriched_sync.destination_connection_ids

        # Return a properly model-validated instance
        return schemas.Sync.model_validate(sync_dict)

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: models.Sync,
        obj_in: Union[SyncUpdate, dict[str, Any]],
        ctx: BaseContext,
        uow: Optional[UnitOfWork] = None,
    ) -> models.Sync:
        """Update a sync.

        Overrides the base update method to automatically calculate next_scheduled_run
        when cron_schedule is updated.

        Args:
            db: The database session
            db_obj: The sync object to update
            obj_in: The update data
            ctx: The API context
            uow: Optional unit of work

        Returns:
            The updated sync
        """
        if not isinstance(obj_in, dict):
            obj_in = obj_in.model_dump(exclude_unset=True)

        # Calculate next_scheduled_run if cron_schedule is being updated
        if "cron_schedule" in obj_in:
            cron_schedule = obj_in["cron_schedule"]
            if cron_schedule is not None:
                try:
                    from datetime import datetime, timezone

                    from croniter import croniter

                    # Create a croniter instance with the cron expression
                    # Use timezone-aware UTC datetime as base
                    base = datetime.now(timezone.utc)
                    iter = croniter(cron_schedule, base)

                    # Get the next run time (will be timezone-aware)
                    next_run_aware = iter.get_next(datetime)
                    # Convert to naive for database storage (PostgreSQL stores as UTC)
                    next_run = next_run_aware.replace(tzinfo=None)
                    obj_in["next_scheduled_run"] = next_run
                except Exception as e:
                    import logging

                    logging.error(f"Error calculating next run time: {e}")
            else:
                # If cron_schedule is None, also set next_scheduled_run to None
                obj_in["next_scheduled_run"] = None

        # Call the parent class update method
        return await super().update(db=db, db_obj=db_obj, obj_in=obj_in, ctx=ctx, uow=uow)


sync = CRUDSync(Sync)
