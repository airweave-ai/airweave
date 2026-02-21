"""Collections API endpoints for managing data collections.

This module provides endpoints for creating, reading, updating, and deleting
collections. Collections are containers that group related data from one or
more source connections, enabling unified search across multiple data sources.
"""

from typing import List

from fastapi import Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.analytics.service import analytics
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.deps import Inject
from airweave.api.examples import (
    create_collection_list_response,
)
from airweave.api.router import TrailingSlashRouter
from airweave.core.collection_service import collection_service
from airweave.core.events.collection import CollectionLifecycleEvent
from airweave.core.protocols import EventBus
from airweave.schemas.errors import (
    NotFoundErrorResponse,
    RateLimitErrorResponse,
    ValidationErrorResponse,
)

router = TrailingSlashRouter()


@router.get(
    "/",
    response_model=List[schemas.Collection],
    summary="List Collections",
    description="""Retrieve all collections belonging to your organization.

Collections are containers that group related data from one or more source
connections, enabling unified search across multiple data sources.

Results are sorted by creation date (newest first) and support pagination
and text search filtering.""",
    responses={
        **create_collection_list_response(["finance_data"], "Finance data collection"),
        422: {"model": ValidationErrorResponse, "description": "Validation Error"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def list(
    skip: int = Query(
        0,
        ge=0,
        description="Number of collections to skip for pagination",
        json_schema_extra={"example": 0},
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of collections to return (1-1000)",
        json_schema_extra={"example": 100},
    ),
    search: str = Query(
        None,
        description="Search term to filter collections by name or readable_id",
        json_schema_extra={"example": "customer"},
    ),
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> List[schemas.Collection]:
    """List all collections belonging to your organization."""
    collections = await crud.collection.get_multi(
        db,
        ctx=ctx,
        skip=skip,
        limit=limit,
        search_query=search,
    )
    return collections


@router.get("/count", response_model=int)
async def count(
    search: str = Query(None, description="Search term to filter by name or readable_id"),
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> int:
    """Get total count of collections for the organization with optional search filtering."""
    return await crud.collection.count(db, ctx=ctx, search_query=search)


@router.post(
    "/",
    response_model=schemas.Collection,
    summary="Create Collection",
    description="""Create a new collection in your organization.

Collections are containers for organizing and searching across data from multiple
sources. After creation, add source connections to begin syncing data.

The collection will be assigned a unique `readable_id` based on the name you provide,
which is used in URLs and API calls. You can optionally configure:

- **Sync schedule**: How frequently to automatically sync data from all sources
- **Custom readable_id**: Provide your own identifier (must be unique and URL-safe)""",
    responses={
        200: {"model": schemas.Collection, "description": "Created collection"},
        422: {"model": ValidationErrorResponse, "description": "Validation Error"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def create(
    collection: schemas.CollectionCreate,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    event_bus: EventBus = Inject(EventBus),
) -> schemas.Collection:
    """Create a new collection."""
    # Create the collection
    collection_obj = await collection_service.create(db, collection_in=collection, ctx=ctx)

    analytics.track_event(
        "collection_created",
        {
            "collection_id": str(collection_obj.id),
            "collection_name": collection_obj.name,
        },
        ctx=ctx,
    )

    # Publish collection.created event
    try:
        await event_bus.publish(
            CollectionLifecycleEvent.created(
                organization_id=ctx.organization.id,
                collection_id=collection_obj.id,
                collection_name=collection_obj.name,
                collection_readable_id=collection_obj.readable_id,
            )
        )
    except Exception as e:
        ctx.logger.warning(f"Failed to publish collection.created event: {e}")

    return collection_obj


@router.get(
    "/{readable_id}",
    response_model=schemas.Collection,
    summary="Get Collection",
    description="""Retrieve details of a specific collection by its readable ID.

Returns the complete collection configuration including sync settings, status,
and metadata. Use this to check the current state of a collection or to get
configuration details before making updates.""",
    responses={
        200: {"model": schemas.Collection, "description": "Collection details"},
        404: {"model": NotFoundErrorResponse, "description": "Collection Not Found"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def get(
    readable_id: str = Path(
        ...,
        description="The unique readable identifier of the collection (e.g., 'finance-data-ab123')",
        json_schema_extra={"example": "customer-support-tickets-x7k9m"},
    ),
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.Collection:
    """Retrieve a specific collection by its readable ID."""
    db_obj = await crud.collection.get_by_readable_id(db, readable_id=readable_id, ctx=ctx)
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return db_obj


@router.patch(
    "/{readable_id}",
    response_model=schemas.Collection,
    summary="Update Collection",
    description="""Update an existing collection's properties.

You can modify:
- **Name**: The display name shown in the UI
- **Sync configuration**: Schedule settings for automatic data synchronization

Note that the `readable_id` cannot be changed after creation to maintain stable
API endpoints and preserve existing integrations.""",
    responses={
        200: {"model": schemas.Collection, "description": "Updated collection"},
        404: {"model": NotFoundErrorResponse, "description": "Collection Not Found"},
        422: {"model": ValidationErrorResponse, "description": "Validation Error"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def update(
    collection: schemas.CollectionUpdate,
    readable_id: str = Path(
        ...,
        description="The unique readable identifier of the collection to update",
        json_schema_extra={"example": "customer-support-tickets-x7k9m"},
    ),
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    event_bus: EventBus = Inject(EventBus),
) -> schemas.Collection:
    """Update a collection's properties."""
    db_obj = await crud.collection.get_by_readable_id(db, readable_id=readable_id, ctx=ctx)
    if db_obj is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    result = await crud.collection.update(db, db_obj=db_obj, obj_in=collection, ctx=ctx)

    # Publish collection.updated event
    try:
        await event_bus.publish(
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


@router.delete(
    "/{readable_id}",
    response_model=schemas.Collection,
    summary="Delete Collection",
    description="""Permanently delete a collection and all associated data.

This operation:
- Removes all synced data from the vector database
- Deletes all source connections within the collection
- Cancels any scheduled sync jobs
- Cleans up all related resources

**Warning**: This action cannot be undone. All data will be permanently deleted.""",
    responses={
        200: {"model": schemas.Collection, "description": "Deleted collection"},
        404: {"model": NotFoundErrorResponse, "description": "Collection Not Found"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def delete(
    readable_id: str = Path(
        ...,
        description="The unique readable identifier of the collection to delete",
        json_schema_extra={"example": "customer-support-tickets-x7k9m"},
    ),
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    event_bus: EventBus = Inject(EventBus),
) -> schemas.Collection:
    """Delete a collection and all associated data."""
    result = await collection_service.delete(
        db,
        readable_id=readable_id,
        ctx=ctx,
    )

    # Publish collection.deleted event
    try:
        await event_bus.publish(
            CollectionLifecycleEvent.deleted(
                organization_id=ctx.organization.id,
                collection_id=result.id,
                collection_name=result.name,
                collection_readable_id=result.readable_id,
            )
        )
    except Exception as e:
        ctx.logger.warning(f"Failed to publish collection.deleted event: {e}")

    return result
