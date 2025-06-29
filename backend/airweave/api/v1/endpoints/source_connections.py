"""API endpoints for managing source connections."""

from typing import List, Optional
from uuid import UUID

from fastapi import BackgroundTasks, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.utils.input_validation import (
    validate_request_data,
    AUTH_CODE_VALIDATION,
    SOURCE_CONNECTION_CREATE_VALIDATION,
)

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.logging import logger
from airweave.core.shared_models import SyncJobStatus
from airweave.core.source_connection_service import source_connection_service
from airweave.core.sync_job_service import sync_job_service
from airweave.core.sync_service import sync_service
from airweave.core.temporal_service import temporal_service
from airweave.db.session import get_db_context
from airweave.schemas.auth import AuthContext

router = TrailingSlashRouter()


@router.get("/", response_model=List[schemas.SourceConnectionListItem])
async def list_source_connections(
    *,
    db: AsyncSession = Depends(deps.get_db),
    collection: Optional[str] = Query(None, description="Filter by collection"),
    skip: int = 0,
    limit: int = 100,
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> List[schemas.SourceConnectionListItem]:
    """List all source connections for the organization.

    Args:
        db: The database session
        collection: The collection to filter by
        skip: The number of connections to skip
        limit: The number of connections to return
        auth_context: The current authentication context

    Returns:
        A list of source connection list items with essential information
    """
    if collection:
        return await source_connection_service.get_source_connections_by_collection(
            db=db,
            collection=collection,
            auth_context=auth_context,
            skip=skip,
            limit=limit,
        )

    return await source_connection_service.get_all_source_connections(
        db=db, auth_context=auth_context, skip=skip, limit=limit
    )


@router.get("/{source_connection_id}", response_model=schemas.SourceConnection)
async def get_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID,
    show_auth_fields: bool = False,
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.SourceConnection:
    """Get a specific source connection by ID.

    Args:
        db: The database session
        source_connection_id: The ID of the source connection
        show_auth_fields: Whether to show the auth fields, default is False
        auth_context: The current authentication context

    Returns:
        The source connection
    """
    return await source_connection_service.get_source_connection(
        db=db,
        source_connection_id=source_connection_id,
        show_auth_fields=show_auth_fields,
        auth_context=auth_context,
    )


@router.post("/", response_model=schemas.SourceConnection)
async def create_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_in: schemas.SourceConnectionCreate = Body(...),
    auth_context: AuthContext = Depends(deps.get_auth_context),
    background_tasks: BackgroundTasks,
) -> schemas.SourceConnection:
    # Validate and sanitize input data
    validated_data = validate_request_data(
        source_connection_in.model_dump(),
        "source_connection_create"
    )
    
    # Update the source_connection_in object with validated data
    for key, value in validated_data.items():
        if hasattr(source_connection_in, key):
            setattr(source_connection_in, key, value)
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
        auth_context: The current authentication context
        background_tasks: Background tasks for async operations

    Returns:
        The created source connection
    """
    source_connection, sync_job = await source_connection_service.create_source_connection(
        db=db, source_connection_in=source_connection_in, auth_context=auth_context
    )

    # If job was created and sync_immediately is True, start it in background
    if sync_job and source_connection_in.sync_immediately:
        async with get_db_context() as db:
            sync_dag = await sync_service.get_sync_dag(
                db=db, sync_id=source_connection.sync_id, auth_context=auth_context
            )

            # Get the sync object
            sync = await crud.sync.get(
                db=db, id=source_connection.sync_id, auth_context=auth_context
            )
            sync = schemas.Sync.model_validate(sync, from_attributes=True)
            sync_dag = schemas.SyncDag.model_validate(sync_dag, from_attributes=True)
            collection = await crud.collection.get_by_readable_id(
                db=db, readable_id=source_connection.collection, auth_context=auth_context
            )
            collection = schemas.Collection.model_validate(collection, from_attributes=True)

            # Get source connection with auth_fields for temporal processing
            source_connection_with_auth = await source_connection_service.get_source_connection(
                db=db,
                source_connection_id=source_connection.id,
                show_auth_fields=True,  # Important: Need actual auth_fields for temporal
                auth_context=auth_context,
            )

            # Check if Temporal is enabled, otherwise fall back to background tasks
            if await temporal_service.is_temporal_enabled():
                # Use Temporal workflow
                await temporal_service.run_source_connection_workflow(
                    sync=sync,
                    sync_job=sync_job,
                    sync_dag=sync_dag,
                    collection=collection,
                    source_connection=source_connection_with_auth,
                    auth_context=auth_context,
                )
            else:
                # Fall back to background tasks
                background_tasks.add_task(
                    sync_service.run,
                    sync,
                    sync_job,
                    sync_dag,
                    collection,
                    source_connection_with_auth,
                    auth_context,
                )

    return source_connection


@router.put("/{source_connection_id}", response_model=schemas.SourceConnection)
async def update_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID,
    source_connection_in: schemas.SourceConnectionUpdate = Body(...),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.SourceConnection:
    """Update a source connection.

    Args:
        db: The database session
        source_connection_id: The ID of the source connection to update
        source_connection_in: The updated source connection data
        auth_context: The current authentication context

    Returns:
        The updated source connection
    """
    return await source_connection_service.update_source_connection(
        db=db,
        source_connection_id=source_connection_id,
        source_connection_in=source_connection_in,
        auth_context=auth_context,
    )


@router.delete("/{source_connection_id}", response_model=schemas.SourceConnection)
async def delete_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID,
    delete_data: bool = False,
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.SourceConnection:
    """Delete a source connection and all related components.

    Args:
        db: The database session
        source_connection_id: The ID of the source connection to delete
        delete_data: Whether to delete the associated data in destinations
        auth_context: The current authentication context

    Returns:
        The deleted source connection
    """
    return await source_connection_service.delete_source_connection(
        db=db,
        source_connection_id=source_connection_id,
        auth_context=auth_context,
        delete_data=delete_data,
    )


@router.post("/{source_connection_id}/run", response_model=schemas.SourceConnectionJob)
async def run_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID,
    access_token: Optional[str] = Body(None, embed=True),
    auth_context: AuthContext = Depends(deps.get_auth_context),
    background_tasks: BackgroundTasks,
) -> schemas.SourceConnectionJob:
    """Trigger a sync run for a source connection.

    Args:
        db: The database session
        source_connection_id: The ID of the source connection to run
        access_token: Optional access token to use instead of stored credentials
        auth_context: The current authentication context
        background_tasks: Background tasks for async operations

    Returns:
        The created sync job
    """
    sync_job = await source_connection_service.run_source_connection(
        db=db,
        source_connection_id=source_connection_id,
        auth_context=auth_context,
        access_token=access_token,
    )

    # Start the sync job in the background
    sync = await crud.sync.get(
        db=db, id=sync_job.sync_id, auth_context=auth_context, with_connections=True
    )
    sync_dag = await sync_service.get_sync_dag(
        db=db, sync_id=sync_job.sync_id, auth_context=auth_context
    )

    # Get source connection with auth_fields for temporal processing
    source_connection_with_auth = await source_connection_service.get_source_connection(
        db=db,
        source_connection_id=source_connection_id,
        show_auth_fields=True,  # Important: Need actual auth_fields for temporal
        auth_context=auth_context,
    )

    collection = await crud.collection.get_by_readable_id(
        db=db, readable_id=source_connection_with_auth.collection, auth_context=auth_context
    )

    sync = schemas.Sync.model_validate(sync, from_attributes=True)
    sync_dag = schemas.SyncDag.model_validate(sync_dag, from_attributes=True)
    collection = schemas.Collection.model_validate(collection, from_attributes=True)

    # Check if Temporal is enabled, otherwise fall back to background tasks
    if await temporal_service.is_temporal_enabled():
        # Use Temporal workflow
        await temporal_service.run_source_connection_workflow(
            sync=sync,
            sync_job=sync_job,
            sync_dag=sync_dag,
            collection=collection,
            source_connection=source_connection_with_auth,
            auth_context=auth_context,
            access_token=sync_job.access_token if hasattr(sync_job, "access_token") else None,
        )
    else:
        # Fall back to background tasks
        background_tasks.add_task(
            sync_service.run,
            sync,
            sync_job,
            sync_dag,
            collection,
            source_connection_with_auth,
            auth_context,
            access_token=sync_job.access_token if hasattr(sync_job, "access_token") else None,
        )

    return sync_job.to_source_connection_job(source_connection_id)


@router.get("/{source_connection_id}/jobs", response_model=List[schemas.SourceConnectionJob])
async def list_source_connection_jobs(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID,
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> List[schemas.SourceConnectionJob]:
    """List all sync jobs for a source connection.

    Args:
        db: The database session
        source_connection_id: The ID of the source connection
        auth_context: The current authentication context

    Returns:
        A list of sync jobs
    """
    return await source_connection_service.get_source_connection_jobs(
        db=db, source_connection_id=source_connection_id, auth_context=auth_context
    )


@router.get("/{source_connection_id}/jobs/{job_id}", response_model=schemas.SourceConnectionJob)
async def get_source_connection_job(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID,
    job_id: UUID,
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.SourceConnectionJob:
    """Get a specific sync job for a source connection.

    Args:
        db: The database session
        source_connection_id: The ID of the source connection
        job_id: The ID of the sync job
        auth_context: The current authentication context

    Returns:
        The sync job
    """
    tmp = await source_connection_service.get_source_connection_job(
        db=db, source_connection_id=source_connection_id, job_id=job_id, auth_context=auth_context
    )
    return tmp


@router.post(
    "/{source_connection_id}/jobs/{job_id}/cancel", response_model=schemas.SourceConnectionJob
)
async def cancel_source_connection_job(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID,
    job_id: UUID,
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.SourceConnectionJob:
    """Cancel a running sync job for a source connection.

    This will send a cancellation signal to the Temporal workflow if enabled.
    The workflow will handle the cancellation and update the job status to CANCELLED.

    Args:
        db: The database session
        source_connection_id: The ID of the source connection
        job_id: The ID of the sync job to cancel
        auth_context: The current authentication context

    Returns:
        The cancelled sync job
    """
    # First verify the job exists and belongs to this source connection
    sync_job = await source_connection_service.get_source_connection_job(
        db=db, source_connection_id=source_connection_id, job_id=job_id, auth_context=auth_context
    )

    # Check if the job is in a cancellable state
    if sync_job.status not in [
        SyncJobStatus.CREATED,
        SyncJobStatus.PENDING,
        SyncJobStatus.IN_PROGRESS,
    ]:
        raise HTTPException(
            status_code=400, detail=f"Cannot cancel job in {sync_job.status} status"
        )

    # If Temporal is enabled, try to cancel the workflow
    if await temporal_service.is_temporal_enabled():
        try:
            cancelled = await temporal_service.cancel_sync_job_workflow(str(job_id))
            if cancelled:
                logger.info(f"Successfully sent cancellation signal for job {job_id}")
            else:
                logger.warning(f"No running Temporal workflow found for job {job_id}")
                # Even if no workflow found, we might want to update the status
                # if it's stuck in IN_PROGRESS or PENDING
                if sync_job.status in [SyncJobStatus.IN_PROGRESS, SyncJobStatus.PENDING]:
                    await sync_job_service.update_status(
                        sync_job_id=job_id,
                        status=SyncJobStatus.CANCELLED,
                        auth_context=auth_context,
                        error="Job cancelled by user",
                        failed_at=utc_now_naive(),  # Using failed_at for cancelled timestamp
                    )
        except Exception as e:
            logger.error(f"Error cancelling Temporal workflow: {e}")
            raise HTTPException(status_code=500, detail="Failed to cancel workflow") from None
    else:
        # For non-Temporal jobs, directly update the status
        # (though background tasks can't really be cancelled)
        await sync_job_service.update_status(
            sync_job_id=job_id,
            status=SyncJobStatus.CANCELLED,
            auth_context=auth_context,
            error="Job cancelled by user",
            failed_at=utc_now_naive(),  # Using failed_at for cancelled timestamp
        )

    # Fetch the updated job
    return await source_connection_service.get_source_connection_job(
        db=db, source_connection_id=source_connection_id, job_id=job_id, auth_context=auth_context
    )


@router.get("/{source_short_name}/oauth2_url", response_model=schemas.OAuth2AuthUrl)
async def get_oauth2_authorization_url(
    *,
    source_short_name: str,
    client_id: Optional[str] = None,
) -> schemas.OAuth2AuthUrl:
    """Get the OAuth2 authorization URL for a source.

    Args:
        source_short_name: The short name of the source
        client_id: The OAuth2 client ID

    Returns:
        The OAuth2 authorization URL
    """
    return await source_connection_service.get_oauth2_authorization_url(
        source_short_name=source_short_name, client_id=client_id
    )


@router.post(
    "/{source_short_name}/code_to_token_credentials",
    response_model=schemas.IntegrationCredentialInDB,
)
async def create_credentials_from_authorization_code(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_short_name: str,
    code: str = Query(..., description="The authorization code to exchange"),
    credential_name: Optional[str] = Body(None),
    credential_description: Optional[str] = Body(None),
    client_id: Optional[str] = Body(None),
    client_secret: Optional[str] = Body(None),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.IntegrationCredentialInDB:
    # Validate incoming parameters
    request_data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    
    # Validate auth code and other parameters
    validated_data = validate_request_data(request_data, "auth_code")
    """Exchange OAuth2 code for a token and create integration credentials.

    This endpoint:
    1. Exchanges the authorization code for a token
    2. Creates and stores integration credentials with the token
    3. Returns the created credential

    Args:
        db: The database session
        source_short_name: The short name of the source
        code: The authorization code to exchange
        credential_name: Optional custom name for the credential
        credential_description: Optional description for the credential
        client_id: Optional client ID to override the default
        client_secret: Optional client secret to override the default
        auth_context: The current authentication context

    Returns:
        The created integration credential
    """
    return await source_connection_service.create_credential_from_oauth2_code(
        db=db,
        source_short_name=source_short_name,
        code=code,
        credential_name=credential_name,
        credential_description=credential_description,
        client_id=client_id,
        client_secret=client_secret,
        auth_context=auth_context,
    )
