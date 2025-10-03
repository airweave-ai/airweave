"""API endpoints for collections."""

from typing import List

from fastapi import BackgroundTasks, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.examples import (
    create_collection_list_response,
    create_job_list_response,
)
from airweave.api.router import TrailingSlashRouter
from airweave.core.collection_service import collection_service
from airweave.core.guard_rail_service import GuardRailService
from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import ActionType
from airweave.core.source_connection_service import source_connection_service
from airweave.core.source_connection_service_helpers import source_connection_helpers
from airweave.core.sync_service import sync_service
from airweave.core.temporal_service import temporal_service

router = TrailingSlashRouter()


@router.get(
    "/",
    response_model=List[schemas.Collection],
    responses=create_collection_list_response(
        ["finance_data"],
        "Finance data collection",
    ),
)
async def list(
    skip: int = Query(0, description="Number of collections to skip for pagination"),
    limit: int = Query(
        100, description="Maximum number of collections to return (1-1000)", le=1000, ge=1
    ),
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> List[schemas.Collection]:
    """List all collections that belong to your organization."""
    collections = await crud.collection.get_multi(
        db,
        ctx=ctx,
        skip=skip,
        limit=limit,
    )
    return collections


@router.post("/", response_model=schemas.Collection)
async def create(
    collection: schemas.CollectionCreate,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.Collection:
    """Create a new collection.

    The newly created collection is initially empty and does not contain any data
    until you explicitly add source connections to it.
    """
    # Create the collection
    collection_obj = await collection_service.create(db, collection_in=collection, ctx=ctx)

    ctx.analytics.track_event(
        "collection_created",
        {
            "collection_id": str(collection_obj.id),
            "collection_name": collection_obj.name,
        },
    )

    return collection_obj


@router.get("/{readable_id}", response_model=schemas.Collection)
async def get(
    readable_id: str = Path(
        ...,
        description="The unique readable identifier of the collection (e.g., 'finance-data-ab123')",
    ),
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.Collection:
    """Retrieve a specific collection by its readable ID."""
    db_obj = await crud.collection.get_by_readable_id(db, readable_id=readable_id, ctx=ctx)
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return db_obj


@router.patch("/{readable_id}", response_model=schemas.Collection)
async def update(
    collection: schemas.CollectionUpdate,
    readable_id: str = Path(
        ..., description="The unique readable identifier of the collection to update"
    ),
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.Collection:
    """Update a collection's properties.

    Modifies the display name of an existing collection.
    Note that the readable ID cannot be changed after creation to maintain stable
    API endpoints and preserve any existing integrations or bookmarks.
    """
    db_obj = await crud.collection.get_by_readable_id(db, readable_id=readable_id, ctx=ctx)
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return await crud.collection.update(db, db_obj=db_obj, obj_in=collection, ctx=ctx)


@router.delete("/{readable_id}", response_model=schemas.Collection)
async def delete(
    readable_id: str = Path(
        ..., description="The unique readable identifier of the collection to delete"
    ),
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.Collection:
    """Delete a collection and all associated data.

    Permanently removes a collection from your organization including all synced data
    from the destination systems. All source connections within this collection
    will also be deleted as part of the cleanup process. This action cannot be undone.
    """
    # Find the collection
    db_obj = await crud.collection.get_by_readable_id(db, readable_id=readable_id, ctx=ctx)
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Delete collection data from shared Qdrant collection
    try:
        from qdrant_client.http import models as rest

        from airweave.platform.destinations.qdrant import QdrantDestination

        destination = await QdrantDestination.create(
            credentials=None,  # Native Qdrant uses settings
            config=None,
            collection_id=db_obj.id,
            organization_id=db_obj.organization_id,
            # vector_size auto-detected based on embedding model configuration
        )
        # Delete all points for this collection from shared collection
        if destination.client:
            await destination.client.delete(
                collection_name=destination.collection_name,
                points_selector=rest.FilterSelector(
                    filter=rest.Filter(
                        must=[
                            rest.FieldCondition(
                                key="airweave_collection_id",
                                match=rest.MatchValue(value=str(db_obj.id)),
                            )
                        ]
                    )
                ),
                wait=True,
            )
            ctx.logger.info(f"Deleted data for collection {db_obj.id} from shared collection")
    except Exception as e:
        ctx.logger.error(f"Error deleting Qdrant collection: {str(e)}")
        # Continue with deletion even if Qdrant deletion fails

    # Delete the collection - CASCADE will handle all child objects
    return await crud.collection.remove(db, id=db_obj.id, ctx=ctx)


@router.post(
    "/{readable_id}/refresh_all",
    response_model=List[schemas.SourceConnectionJob],
    responses=create_job_list_response(["completed"], "Multiple sync jobs triggered"),
)
async def refresh_all_source_connections(
    *,
    readable_id: str = Path(
        ..., description="The unique readable identifier of the collection to refresh"
    ),
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
    background_tasks: BackgroundTasks,
    logger: ContextualLogger = Depends(deps.get_logger),
) -> List[schemas.SourceConnectionJob]:
    """Trigger data synchronization for all source connections in the collection.

    The sync jobs run asynchronously in the background, so this endpoint
    returns immediately with job details that you can use to track progress. You can
    monitor the status of individual data synchronization using the source connection
    endpoints.
    """
    # Check if collection exists
    collection = await crud.collection.get_by_readable_id(db, readable_id=readable_id, ctx=ctx)
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Convert to Pydantic model immediately
    collection_obj = schemas.Collection.model_validate(collection, from_attributes=True)

    # Get all source connections for this collection
    source_connections = await source_connection_service.get_source_connections_by_collection(
        db=db, collection=readable_id, ctx=ctx
    )

    if not source_connections:
        return []

    # Check if we're allowed to process entities
    await guard_rail.is_allowed(ActionType.ENTITIES)

    # Create a sync job for each source connection and run it in the background
    sync_jobs = []

    for sc in source_connections:
        # Create the sync job
        sync_job = await source_connection_service.run_source_connection(
            db=db, source_connection_id=sc.id, ctx=ctx
        )

        # Get necessary objects for running the sync
        sync = await crud.sync.get(db=db, id=sync_job.sync_id, ctx=ctx, with_connections=True)
        sync_dag = await sync_service.get_sync_dag(db=db, sync_id=sync_job.sync_id, ctx=ctx)

        # Get source connection with auth_fields for temporal processing
        source_connection = await source_connection_service.get_source_connection(
            db=db,
            source_connection_id=sc.id,
            show_auth_fields=True,  # Important: Need actual auth_fields for temporal
            ctx=ctx,
        )

        # Prepare objects for background task
        sync = schemas.Sync.model_validate(sync, from_attributes=True)
        sync_dag = schemas.SyncDag.model_validate(sync_dag, from_attributes=True)
        source_connection = schemas.SourceConnection.from_orm_with_collection_mapping(
            source_connection
        )

        # Add to jobs list
        sync_jobs.append(sync_job.to_source_connection_job(sc.id))

        try:
            # Start the sync job in the background or via Temporal
            if await temporal_service.is_temporal_enabled():
                # Get the Connection object (not SourceConnection)
                connection_schema = (
                    await source_connection_helpers.get_connection_for_source_connection(
                        db=db, source_connection=sc, ctx=ctx
                    )
                )
                # Use Temporal workflow
                await temporal_service.run_source_connection_workflow(
                    sync=sync,
                    sync_job=sync_job,
                    sync_dag=sync_dag,
                    collection=collection_obj,  # Use the already converted object
                    connection=connection_schema,  # Pass Connection, not SourceConnection
                    ctx=ctx,
                )
            else:
                # Fall back to background tasks
                background_tasks.add_task(
                    sync_service.run,
                    sync,
                    sync_job,
                    sync_dag,
                    collection_obj,  # Use the already converted object
                    source_connection,
                    ctx,
                )

        except Exception as e:
            # Log the error but continue with other source connections
            logger.error(f"Failed to create sync job for source connection {sc.id}: {e}")

    return sync_jobs
