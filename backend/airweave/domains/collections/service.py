"""Collection service — domain logic for collection lifecycle."""

from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.config import Settings
from airweave.core.events.collection import CollectionLifecycleEvent
from airweave.core.protocols.event_bus import EventBus
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.collections.exceptions import (
    CollectionAlreadyExistsError,
    CollectionNotFoundError,
)
from airweave.domains.collections.protocols import (
    CollectionRepositoryProtocol,
    CollectionServiceProtocol,
)
from airweave.domains.source_connections.protocols import SourceConnectionRepositoryProtocol
from airweave.domains.syncs.protocols import SyncLifecycleServiceProtocol
from airweave.models.collection import Collection
from airweave.platform.embedders.config import get_default_provider, get_embedding_model


class CollectionService(CollectionServiceProtocol):
    """Domain service for collection lifecycle operations."""

    def __init__(
        self,
        collection_repo: CollectionRepositoryProtocol,
        sc_repo: SourceConnectionRepositoryProtocol,
        sync_lifecycle: SyncLifecycleServiceProtocol,
        event_bus: EventBus,
        settings: Settings,
    ) -> None:
        """Initialize with injected dependencies."""
        self._collection_repo = collection_repo
        self._sc_repo = sc_repo
        self._sync_lifecycle = sync_lifecycle
        self._event_bus = event_bus
        self._settings = settings

    async def list(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        skip: int = 0,
        limit: int = 100,
        search_query: Optional[str] = None,
    ) -> List[Collection]:
        """List collections with pagination and optional search."""
        return await self._collection_repo.get_multi(
            db, ctx=ctx, skip=skip, limit=limit, search_query=search_query
        )

    async def count(
        self, db: AsyncSession, *, ctx: ApiContext, search_query: Optional[str] = None
    ) -> int:
        """Get total count of collections."""
        return await self._collection_repo.count(db, ctx=ctx, search_query=search_query)

    async def create(
        self,
        db: AsyncSession,
        *,
        collection_in: schemas.CollectionCreate,
        ctx: ApiContext,
    ) -> schemas.Collection:
        """Create a new collection with embedding config."""
        # Check for duplicate readable_id
        existing = await self._collection_repo.get_by_readable_id(
            db, collection_in.readable_id, ctx
        )
        if existing:
            raise CollectionAlreadyExistsError(collection_in.readable_id)

        # Resolve embedding config
        vector_size = self._settings.EMBEDDING_DIMENSIONS
        embedding_provider = get_default_provider()
        embedding_model_name = get_embedding_model(embedding_provider)

        collection_data = collection_in.model_dump()
        collection_data["vector_size"] = vector_size
        collection_data["embedding_model_name"] = embedding_model_name

        async with UnitOfWork(db) as uow:
            collection = await self._collection_repo.create(
                db, obj_in=collection_data, ctx=ctx, uow=uow
            )
            await uow.session.flush()
            result = schemas.Collection.model_validate(collection, from_attributes=True)

        # Publish event
        try:
            await self._event_bus.publish(
                CollectionLifecycleEvent.created(
                    organization_id=ctx.organization.id,
                    collection_id=result.id,
                    collection_name=result.name,
                    collection_readable_id=result.readable_id,
                )
            )
        except Exception as e:
            ctx.logger.warning(f"Failed to publish collection.created event: {e}")

        return result

    async def get(self, db: AsyncSession, *, readable_id: str, ctx: ApiContext) -> Collection:
        """Get a collection by readable ID."""
        db_obj = await self._collection_repo.get_by_readable_id(db, readable_id, ctx)
        if db_obj is None:
            raise CollectionNotFoundError(readable_id)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        readable_id: str,
        collection_in: schemas.CollectionUpdate,
        ctx: ApiContext,
    ) -> Collection:
        """Update a collection by readable ID."""
        db_obj = await self._collection_repo.get_by_readable_id(db, readable_id, ctx)
        if db_obj is None:
            raise CollectionNotFoundError(readable_id)

        result = await self._collection_repo.update(
            db, db_obj=db_obj, obj_in=collection_in, ctx=ctx
        )

        try:
            await self._event_bus.publish(
                CollectionLifecycleEvent.updated(
                    organization_id=ctx.organization.id,
                    collection_id=result.id,
                    collection_name=result.name,
                    collection_readable_id=result.readable_id,
                )
            )
        except Exception as e:
            ctx.logger.warning(f"Failed to publish collection.updated event: {e}")

        return result

    async def delete(
        self, db: AsyncSession, *, readable_id: str, ctx: ApiContext
    ) -> schemas.Collection:
        """Delete a collection and all related data."""
        db_obj = await self._collection_repo.get_by_readable_id(db, readable_id, ctx)
        if db_obj is None:
            raise CollectionNotFoundError(readable_id)

        collection_id = db_obj.id
        organization_id = ctx.organization.id

        # Snapshot while session is fresh (teardown expires all objects via db.expire_all)
        result = schemas.Collection.model_validate(db_obj, from_attributes=True)

        # Collect sync IDs before CASCADE removes them
        sync_ids = await self._sc_repo.get_sync_ids_for_collection(
            db, organization_id=organization_id, readable_collection_id=result.readable_id
        )

        # Cancel running workflows and wait for workers to stop
        await self._sync_lifecycle.teardown_syncs_for_collection(
            db,
            sync_ids=sync_ids,
            collection_id=collection_id,
            organization_id=organization_id,
            ctx=ctx,
        )

        # CASCADE-delete the collection and all child objects
        await self._collection_repo.remove(db, id=collection_id, ctx=ctx)

        # Publish event
        try:
            await self._event_bus.publish(
                CollectionLifecycleEvent.deleted(
                    organization_id=organization_id,
                    collection_id=result.id,
                    collection_name=result.name,
                    collection_readable_id=result.readable_id,
                )
            )
        except Exception as e:
            ctx.logger.warning(f"Failed to publish collection.deleted event: {e}")

        return result
