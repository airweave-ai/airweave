"""Collection service."""

import asyncio
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException
from airweave.core.shared_models import SyncJobStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.source_connection import SourceConnection
from airweave.platform.destinations.vespa import VespaDestination
from airweave.platform.sync.config.base import SyncConfig


class CollectionService:
    """Service for managing collections.

    Manages the lifecycle of collections across the SQL datamodel and destinations.
    """

    async def create(
        self,
        db: AsyncSession,
        collection_in: schemas.CollectionCreate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> schemas.Collection:
        """Create a new collection."""
        if uow is None:
            # Unit of work is not provided, so we create a new one
            async with UnitOfWork(db) as uow:
                collection = await self._create(db, collection_in=collection_in, ctx=ctx, uow=uow)
        else:
            # Unit of work is provided, so we just create the collection
            collection = await self._create(db, collection_in=collection_in, ctx=ctx, uow=uow)

        return collection

    async def _create(
        self,
        db: AsyncSession,
        collection_in: schemas.CollectionCreate,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> schemas.Collection:
        """Create a new collection."""
        from airweave.platform.embedders.config import (
            get_default_provider,
            get_embedding_model,
        )

        # Check if the collection already exists
        try:
            existing_collection = await crud.collection.get_by_readable_id(
                db, readable_id=collection_in.readable_id, ctx=ctx
            )
        except NotFoundException:
            existing_collection = None

        if existing_collection:
            raise HTTPException(
                status_code=400, detail="Collection with this readable_id already exists"
            )

        # Determine vector size and embedding model for this collection
        vector_size = settings.EMBEDDING_DIMENSIONS
        embedding_provider = get_default_provider()
        embedding_model_name = get_embedding_model(embedding_provider)

        # Add vector_size and embedding_model_name to collection data
        collection_data = collection_in.model_dump()
        collection_data["vector_size"] = vector_size
        collection_data["embedding_model_name"] = embedding_model_name

        collection = await crud.collection.create(db, obj_in=collection_data, ctx=ctx, uow=uow)
        await uow.session.flush()

        # Get sync config to determine which vector DBs are enabled
        sync_config = SyncConfig()

        # Initialize Vespa destination if not skipped
        if not sync_config.destinations.skip_vespa:
            try:
                vespa_destination = await VespaDestination.create(
                    credentials=None,
                    config=None,
                    collection_id=collection.id,
                    organization_id=ctx.organization.id,
                    vector_size=vector_size,
                    logger=ctx.logger,
                    sync_id=None,
                )
                await vespa_destination.setup_collection()
            except Exception as e:
                ctx.logger.warning(f"Vespa setup skipped (may not be configured): {e}")

        return schemas.Collection.model_validate(collection, from_attributes=True)

    async def delete(
        self,
        db: AsyncSession,
        *,
        readable_id: str,
        ctx: ApiContext,
    ) -> schemas.Collection:
        """Delete a collection and all related data.

        The flow is:
        1. Collect sync IDs before CASCADE removes them.
        2. Cancel any running sync workflows and wait for workers to stop.
        3. CASCADE-delete the DB records (collection, source connections, etc.).
        4. Fire-and-forget a Temporal cleanup workflow for the slow external
           data deletion (Vespa, ARF, schedules).

        Args:
            db: Database session.
            readable_id: Collection readable ID.
            ctx: API context.

        Returns:
            The deleted collection schema.
        """
        db_obj = await crud.collection.get_by_readable_id(db, readable_id=readable_id, ctx=ctx)
        if db_obj is None:
            raise HTTPException(status_code=404, detail="Collection not found")

        # Capture IDs before deletion (ORM objects become stale after barrier)
        collection_id = db_obj.id
        organization_id = ctx.organization.id

        # Collect sync IDs before CASCADE deletes remove the rows
        sync_ids = await self._get_sync_ids_for_collection(
            db, organization_id=organization_id, readable_collection_id=db_obj.readable_id
        )

        # Cancel running workflows and wait for workers to stop writing
        await self._cancel_and_wait_for_syncs(db, sync_ids, ctx)

        # CASCADE-delete the collection and all child objects
        result = await crud.collection.remove(db, id=collection_id, ctx=ctx)

        # Fire-and-forget: async cleanup of Vespa, ARF, Temporal schedules
        await self._schedule_async_cleanup(sync_ids, collection_id, organization_id, ctx)

        return result

    # -------------------------------------------------------------------------
    # Private: Deletion helpers
    # -------------------------------------------------------------------------

    async def _get_sync_ids_for_collection(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        readable_collection_id: str,
    ) -> List[UUID]:
        """Get all sync IDs for source connections in a collection."""
        rows = await db.execute(
            select(SourceConnection.sync_id)
            .where(
                SourceConnection.organization_id == organization_id,
                SourceConnection.readable_collection_id == readable_collection_id,
                SourceConnection.sync_id.is_not(None),
            )
            .distinct()
        )
        return [row[0] for row in rows if row[0]]

    async def _cancel_and_wait_for_syncs(
        self,
        db: AsyncSession,
        sync_ids: List[UUID],
        ctx: ApiContext,
        timeout_seconds: int = 15,
    ) -> None:
        """Cancel running workflows and wait for them to reach terminal state.

        Sends Temporal cancel signals for PENDING/RUNNING jobs, then polls until
        all non-terminal jobs complete. Jobs already in CANCELLING state are waited
        on without sending a new signal.
        """
        non_terminal = {SyncJobStatus.PENDING, SyncJobStatus.RUNNING, SyncJobStatus.CANCELLING}
        terminal = {SyncJobStatus.COMPLETED, SyncJobStatus.FAILED, SyncJobStatus.CANCELLED}

        syncs_to_wait = []
        for sync_id in sync_ids:
            latest_job = await crud.sync_job.get_latest_by_sync_id(db, sync_id=sync_id)
            if not latest_job or latest_job.status not in non_terminal:
                continue

            if latest_job.status in [SyncJobStatus.PENDING, SyncJobStatus.RUNNING]:
                from airweave.core.temporal_service import temporal_service

                try:
                    await temporal_service.cancel_sync_job_workflow(str(latest_job.id), ctx)
                    ctx.logger.info(f"Cancelled job {latest_job.id} before deletion")
                except Exception as e:
                    ctx.logger.warning(f"Failed to cancel job {latest_job.id}: {e}")

            syncs_to_wait.append(sync_id)

        if not syncs_to_wait:
            return

        elapsed = 0.0
        while elapsed < timeout_seconds and syncs_to_wait:
            await asyncio.sleep(1.0)
            elapsed += 1.0
            db.expire_all()
            still_waiting = []
            for sid in syncs_to_wait:
                job = await crud.sync_job.get_latest_by_sync_id(db, sync_id=sid)
                if job and job.status not in terminal:
                    still_waiting.append(sid)
            syncs_to_wait = still_waiting

        if syncs_to_wait:
            ctx.logger.warning(
                f"{len(syncs_to_wait)} sync(s) did not reach terminal state "
                f"within {timeout_seconds}s -- proceeding with deletion anyway"
            )

    async def _schedule_async_cleanup(
        self,
        sync_ids: List[UUID],
        collection_id: UUID,
        organization_id: UUID,
        ctx: ApiContext,
    ) -> None:
        """Schedule a Temporal workflow for async Vespa/ARF cleanup."""
        if not sync_ids:
            return

        from airweave.core.temporal_service import temporal_service

        try:
            await temporal_service.start_cleanup_sync_data_workflow(
                sync_ids=[str(sid) for sid in sync_ids],
                collection_id=str(collection_id),
                organization_id=str(organization_id),
                ctx=ctx,
            )
        except Exception as e:
            ctx.logger.error(
                f"Failed to schedule async cleanup for collection {collection_id}: {e}. "
                f"Data may be orphaned in Vespa/ARF."
            )


# Singleton instance
collection_service = CollectionService()
