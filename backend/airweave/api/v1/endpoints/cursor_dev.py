"""API endpoints for Cursor development tooling.

These endpoints are only enabled when LOCAL_CURSOR_DEVELOPMENT is True.
"""

from typing import List

from fastapi import BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.core.shared_models import ConnectionStatus, IntegrationType
from airweave.core.sync_service import sync_service
from airweave.db.unit_of_work import UnitOfWork
from airweave.platform.auth.settings import integration_settings

router = TrailingSlashRouter()


@router.get("/connections/status/{short_name}", response_model=List[schemas.Connection])
async def check_connection_status(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
) -> List[schemas.Connection]:
    """Check if a source connection exists for the given short_name.

    Args:
    -----
        db: The database session
        short_name: The short name of the source to check
        user: The admin user

    Returns:
    --------
        List[schemas.Connection]: List of source connections for the given short_name

    """
    try:
        integration_settings.get_by_short_name(short_name)
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Integration {short_name} not found in the integration settings. "
                "Please add the client id and client secret for the integration in the "
                "backend/airweave/platform/auth/yaml/dev.integrations.yaml file, then restart the "
                "backend server and make a connection through the UI."
            ),
        ) from e

    # Find source connections for the given short_name
    connections = await crud.connection.get_all_by_short_name(db=db, short_name=short_name)

    # Filter for SOURCE connections only
    source_connections = [
        conn for conn in connections if conn.integration_type == IntegrationType.SOURCE
    ]

    if not source_connections:
        raise HTTPException(
            status_code=404,
            detail=f"No source connections found for source with short_name: {short_name}",
        )

    return source_connections


@router.post("/test-sync/{short_name}", response_model=schemas.SyncJob)
async def test_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
    background_tasks: BackgroundTasks,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.SyncJob:
    """Run a sync for a specific source by short_name.

    This endpoint is used for testing source integrations during development.
    It finds the first available source connection for the given short_name and
    runs a sync on it.

    Args:
    -----
        db: The database session
        short_name: The short name of the source to sync
        background_tasks: The background tasks
        user: The admin user

    Returns:
    --------
        schemas.SyncJob: The created sync job
    """
    # Find a source connection for the given short_name
    connections = await crud.connection.get_all_by_short_name(db=db, short_name=short_name)

    # Filter for SOURCE connections only
    source_connections = [
        conn for conn in connections if conn.integration_type == IntegrationType.SOURCE
    ]

    # Filter for active source connections
    active_source_connections = [
        conn for conn in source_connections if conn.status == ConnectionStatus.ACTIVE
    ]

    if not active_source_connections:
        raise HTTPException(
            status_code=404,
            detail=f"No active source connections found for source with short_name: {short_name}",
        )

    # Use the first available connection
    source_connection = active_source_connections[0]

    # Create a new sync
    async with UnitOfWork(db) as uow:
        # Create a sync using the first destination found
        sync_in = schemas.SyncCreate(
            name=f"Test Sync for {short_name}",
            source_connection_id=source_connection.id,
        )

        sync = await sync_service.create(db=db, sync=sync_in.to_base(), current_user=user, uow=uow)
        await uow.session.flush()

        # Create a sync job
        sync_job_in = schemas.SyncJobCreate(sync_id=sync.id)
        sync_job = await crud.sync_job.create(db=db, obj_in=sync_job_in, current_user=user, uow=uow)
        await uow.session.flush()  # Flush to ensure created_at and modified_at are populated

        # Get the DAG
        sync_dag = await crud.sync_dag.get_by_sync_id(db=db, sync_id=sync.id, current_user=user)

        # Convert models to schemas
        sync_schema = schemas.Sync.model_validate(sync)
        sync_job_schema = schemas.SyncJob.model_validate(sync_job)
        sync_dag_schema = schemas.SyncDag.model_validate(sync_dag)
        user_schema = schemas.User.model_validate(user)

    _ = await sync_service.run(sync_schema, sync_job_schema, sync_dag_schema, user_schema)

    return sync_job_schema
