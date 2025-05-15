"""API endpoints for managing source connections."""

from typing import List, Optional
from uuid import UUID

from fastapi import BackgroundTasks, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.core.source_connection_service import source_connection_service
from airweave.core.sync_service import sync_service
from airweave.db.session import get_db_context

router = TrailingSlashRouter()


@router.get("/", response_model=List[schemas.SourceConnectionListItem])
async def list_source_connections(
    *,
    db: AsyncSession = Depends(deps.get_db),
    collection: Optional[str] = Query(None, description="Filter by collection"),
    skip: int = 0,
    limit: int = 100,
    user: schemas.User = Depends(deps.get_user),
) -> List[schemas.SourceConnectionListItem]:
    """List all source connections for the current user.

    Args:
        db: The database session
        collection: The collection to filter by
        skip: The number of connections to skip
        limit: The number of connections to return
        user: The current user

    Returns:
        A list of source connection list items with essential information
    """
    if collection:
        return await source_connection_service.get_source_connections_by_collection(
            db=db,
            collection=collection,
            current_user=user,
            skip=skip,
            limit=limit,
        )

    return await source_connection_service.get_all_source_connections(
        db=db, current_user=user, skip=skip, limit=limit
    )


@router.get("/{source_connection_id}", response_model=schemas.SourceConnection)
async def get_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID,
    show_auth_fields: bool = False,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.SourceConnection:
    """Get a specific source connection by ID.

    Args:
        db: The database session
        source_connection_id: The ID of the source connection
        show_auth_fields: Whether to show the auth fields, default is False
        user: The current user

    Returns:
        The source connection
    """
    return await source_connection_service.get_source_connection(
        db=db,
        source_connection_id=source_connection_id,
        show_auth_fields=show_auth_fields,
        current_user=user,
    )


@router.post("/", response_model=schemas.SourceConnection)
async def create_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_in: schemas.SourceConnectionCreate = Body(...),
    user: schemas.User = Depends(deps.get_user),
    background_tasks: BackgroundTasks,
) -> schemas.SourceConnection:
    """Create a new source connection.

    This endpoint creates:
    1. An integration credential with the provided auth fields
    2. A collection if not provided
    3. The source connection
    4. A sync configuration and DAG
    5. A sync job if immediate execution is requested

    Args:
        db: The database session
        source_connection_in: The source connection to create
        user: The current user
        background_tasks: Background tasks for async operations

    Returns:
        The created source connection
    """
    source_connection, sync_job = await source_connection_service.create_source_connection(
        db=db, source_connection_in=source_connection_in, current_user=user
    )

    async with get_db_context() as db:
        # If job was created and sync_immediately is True, start it in background
        if sync_job and source_connection_in.sync_immediately:
            sync_dag = await sync_service.get_sync_dag(
                db=db, sync_id=source_connection.sync_id, current_user=user
            )

            # Get the sync object
            sync = await crud.sync.get(db=db, id=source_connection.sync_id, current_user=user)
            sync = schemas.Sync.model_validate(sync, from_attributes=True)
            sync_job = schemas.SyncJob.model_validate(sync_job, from_attributes=True)
            sync_dag = schemas.SyncDag.model_validate(sync_dag, from_attributes=True)
            collection = await crud.collection.get_by_readable_id(
                db=db, readable_id=source_connection.collection, current_user=user
            )
            collection = schemas.Collection.model_validate(collection, from_attributes=True)
    background_tasks.add_task(
        sync_service.run, sync, sync_job, sync_dag, collection, source_connection, user
    )

    return source_connection


@router.put("/{source_connection_id}", response_model=schemas.SourceConnection)
async def update_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID,
    source_connection_in: schemas.SourceConnectionUpdate = Body(...),
    user: schemas.User = Depends(deps.get_user),
) -> schemas.SourceConnection:
    """Update a source connection.

    Args:
        db: The database session
        source_connection_id: The ID of the source connection to update
        source_connection_in: The updated source connection data
        user: The current user

    Returns:
        The updated source connection
    """
    return await source_connection_service.update_source_connection(
        db=db,
        source_connection_id=source_connection_id,
        source_connection_in=source_connection_in,
        current_user=user,
    )


@router.delete("/{source_connection_id}", response_model=schemas.SourceConnection)
async def delete_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID,
    delete_data: bool = False,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.SourceConnection:
    """Delete a source connection and all related components.

    Args:
        db: The database session
        source_connection_id: The ID of the source connection to delete
        delete_data: Whether to delete the associated data in destinations
        user: The current user

    Returns:
        The deleted source connection
    """
    return await source_connection_service.delete_source_connection(
        db=db, source_connection_id=source_connection_id, current_user=user, delete_data=delete_data
    )


@router.post("/{source_connection_id}/run", response_model=schemas.SourceConnectionJob)
async def run_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID,
    user: schemas.User = Depends(deps.get_user),
    background_tasks: BackgroundTasks,
) -> schemas.SourceConnectionJob:
    """Trigger a sync run for a source connection.

    Args:
        db: The database session
        source_connection_id: The ID of the source connection to run
        user: The current user
        background_tasks: Background tasks for async operations

    Returns:
        The created sync job
    """
    sync_job = await source_connection_service.run_source_connection(
        db=db, source_connection_id=source_connection_id, current_user=user
    )

    # Start the sync job in the background
    sync = await crud.sync.get(db=db, id=sync_job.sync_id, current_user=user, with_connections=True)
    sync_dag = await sync_service.get_sync_dag(db=db, sync_id=sync_job.sync_id, current_user=user)
    source_connection = await crud.source_connection.get(
        db=db, id=source_connection_id, current_user=user
    )
    collection = await crud.collection.get_by_readable_id(
        db=db, readable_id=source_connection.readable_collection_id, current_user=user
    )

    sync = schemas.Sync.model_validate(sync, from_attributes=True)
    sync_dag = schemas.SyncDag.model_validate(sync_dag, from_attributes=True)
    collection = schemas.Collection.model_validate(collection, from_attributes=True)
    source_connection = schemas.SourceConnection.from_orm_with_collection_mapping(source_connection)

    background_tasks.add_task(
        sync_service.run, sync, sync_job, sync_dag, collection, source_connection, user
    )

    return sync_job.to_source_connection_job(source_connection_id)


@router.get("/{source_connection_id}/jobs", response_model=List[schemas.SourceConnectionJob])
async def list_source_connection_jobs(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> List[schemas.SourceConnectionJob]:
    """List all sync jobs for a source connection.

    Args:
        db: The database session
        source_connection_id: The ID of the source connection
        user: The current user

    Returns:
        A list of sync jobs
    """
    return await source_connection_service.get_source_connection_jobs(
        db=db, source_connection_id=source_connection_id, current_user=user
    )


@router.get("/{source_connection_id}/jobs/{job_id}", response_model=schemas.SourceConnectionJob)
async def get_source_connection_job(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID,
    job_id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.SourceConnectionJob:
    """Get a specific sync job for a source connection.

    Args:
        db: The database session
        source_connection_id: The ID of the source connection
        job_id: The ID of the sync job
        user: The current user

    Returns:
        The sync job
    """
    return await source_connection_service.get_source_connection_job(
        db=db, source_connection_id=source_connection_id, job_id=job_id, current_user=user
    )
