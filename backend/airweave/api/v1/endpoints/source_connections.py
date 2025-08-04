"""API endpoints for managing source connections."""

from typing import List, Optional
from uuid import UUID

from fastapi import BackgroundTasks, Body, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.examples import (
    create_job_list_response,
    create_single_job_response,
    create_source_connection_list_response,
)
from airweave.api.router import TrailingSlashRouter
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.logging import logger
from airweave.core.shared_models import SyncJobStatus
from airweave.core.source_connection_service import source_connection_service
from airweave.core.sync_job_service import sync_job_service
from airweave.core.sync_service import sync_service
from airweave.core.temporal_service import temporal_service
from airweave.db.session import get_db_context
from airweave.platform.auth_providers.composio import COMPOSIO_BLOCKED_SOURCES
from airweave.schemas.auth import AuthContext

router = TrailingSlashRouter()


@router.get(
    "/",
    response_model=List[schemas.SourceConnectionListItem],
    responses=create_source_connection_list_response(
        ["engineering_docs"], "Multiple source connections across collections"
    ),
)
async def list_source_connections(
    *,
    db: AsyncSession = Depends(deps.get_db),
    collection: Optional[str] = Query(
        None, description="Filter source connections by collection readable ID"
    ),
    skip: int = Query(0, description="Number of source connections to skip for pagination"),
    limit: int = Query(
        100, description="Maximum number of source connections to return (1-1000)", le=1000, ge=1
    ),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> List[schemas.SourceConnectionListItem]:
    """List source connections across your organization.

    <br/><br/>
    By default, returns ALL source connections from every collection in your
    organization. Use the 'collection' parameter to filter results to a specific
    collection. This is useful for getting an overview of all your data sources
    or managing connections within a particular collection.
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
    source_connection_id: UUID = Path(
        ..., description="The unique identifier of the source connection"
    ),
    show_auth_fields: bool = Query(
        False,
        description="Whether to reveal authentication credentials.",
    ),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.SourceConnection:
    """Retrieve a specific source connection by its ID."""
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
    """Create a new source connection to sync data into your collection.

    <br/><br/>

    **This endpoint only works for sources that do not use OAuth2.0.**
    Sources that do use OAuth2.0 like Google Drive, Slack, or HubSpot must be
    connected through the UI where you can complete the OAuth consent flow.<br/><br/>

    Credentials for a source have to be provided using the `auth_fields` field.
    Currently, it is not automatically checked if the provided credentials are valid.
    If they are not valid, the data synchronization will fail.<br/><br/>

    Check the documentation of a specific source (for example
    [Github](https://docs.airweave.ai/docs/connectors/github)) to see what kind
    of authentication is used.
    """
    if (
        source_connection_in.auth_provider
        and source_connection_in.short_name in COMPOSIO_BLOCKED_SOURCES
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                f"The {source_connection_in.short_name.title()} source cannot currently be created "
                f"using auth providers. Please provide credentials directly using the 'auth_fields'"
                f" parameter instead. Support for {source_connection_in.short_name.title()} through"
                f" auth providers is coming soon."
            ),
        )

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


@router.post("/internal/", response_model=schemas.SourceConnection)
async def create_source_connection_with_credential(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_in: schemas.SourceConnectionCreateWithCredential = Body(...),
    auth_context: AuthContext = Depends(deps.get_auth_context),
    background_tasks: BackgroundTasks,
) -> schemas.SourceConnection:
    """Create a new source connection using an existing credential (internal use only).

    This endpoint is designed for internal frontend use where credentials have already
    been created through OAuth flows or other authentication processes. It should NOT
    be exposed in public API documentation.

    This endpoint:
    1. Uses an existing integration credential (by credential_id)
    2. Creates a collection if not provided
    3. Creates the source connection
    4. Creates a sync configuration and DAG
    5. Creates a sync job if immediate execution is requested

    Args:
        db: The database session
        source_connection_in: The source connection to create with credential_id
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
    source_connection_id: UUID = Path(
        ..., description="The unique identifier of the source connection to update"
    ),
    source_connection_in: schemas.SourceConnectionUpdate = Body(...),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.SourceConnection:
    """Update a source connection's properties.

    <br/><br/>

    Modify the configuration of an existing source connection including its name,
    authentication credentials, configuration fields, sync schedule, or source-specific settings.
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
    source_connection_id: UUID = Path(
        ..., description="The unique identifier of the source connection to delete"
    ),
    delete_data: bool = Query(
        False,
        description="Whether to also delete all synced data from destination systems",
    ),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.SourceConnection:
    """Delete a source connection.

    <br/><br/>

    Permanently removes the source connection configuration and credentials.
    By default, previously synced data remains in your destination systems for continuity.
    Use delete_data=true to also remove all associated data from destination systems.
    """
    return await source_connection_service.delete_source_connection(
        db=db,
        source_connection_id=source_connection_id,
        auth_context=auth_context,
        delete_data=delete_data,
    )


@router.post(
    "/{source_connection_id}/run",
    response_model=schemas.SourceConnectionJob,
    responses=create_single_job_response("completed", "Sync job successfully triggered"),
)
async def run_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID = Path(
        ..., description="The unique identifier of the source connection to sync"
    ),
    access_token: Optional[str] = Body(
        None,
        embed=True,
        description=(
            "This parameter gives you the ability to start a sync job with an access "
            "token for an OAuth2.0 source directly instead of using the credentials "
            "that Airweave has stored for you. Learn more about direct token injection "
            "[here](https://docs.airweave.ai/direct-token-injection)."
        ),
        examples=[
            "ya29.a0AfH6SMBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "gho_abcdefghijklmnopqrstuvwxyz1234567890",
            "sk-1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQR",
        ],
    ),
    auth_context: AuthContext = Depends(deps.get_auth_context),
    background_tasks: BackgroundTasks,
) -> schemas.SourceConnectionJob:
    """Manually trigger a data sync for this source connection.

    <br/><br/>
    Starts an immediate synchronization job that extracts fresh data from your source,
    transforms it according to your configuration, and updates the destination systems.
    The job runs asynchronously and endpoint returns immediately with tracking information.
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


@router.get(
    "/{source_connection_id}/jobs",
    response_model=List[schemas.SourceConnectionJob],
    responses=create_job_list_response(["completed"], "Complete sync job history"),
)
async def list_source_connection_jobs(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID = Path(
        ..., description="The unique identifier of the source connection"
    ),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> List[schemas.SourceConnectionJob]:
    """List all sync jobs for a source connection.

    <br/><br/>
    Returns the complete history of data synchronization jobs including successful syncs,
    failed attempts, and currently running operations.
    """
    return await source_connection_service.get_source_connection_jobs(
        db=db, source_connection_id=source_connection_id, auth_context=auth_context
    )


@router.get(
    "/{source_connection_id}/jobs/{job_id}",
    response_model=schemas.SourceConnectionJob,
    responses=create_single_job_response("completed", "Detailed sync job information"),
)
async def get_source_connection_job(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID = Path(
        ..., description="The unique identifier of the source connection"
    ),
    job_id: UUID = Path(..., description="The unique identifier of the sync job"),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.SourceConnectionJob:
    """Get detailed information about a specific sync job."""
    tmp = await source_connection_service.get_source_connection_job(
        db=db, source_connection_id=source_connection_id, job_id=job_id, auth_context=auth_context
    )
    return tmp


@router.post(
    "/{source_connection_id}/jobs/{job_id}/cancel",
    response_model=schemas.SourceConnectionJob,
    responses=create_single_job_response("cancelled", "Successfully cancelled sync job"),
)
async def cancel_source_connection_job(
    *,
    db: AsyncSession = Depends(deps.get_db),
    source_connection_id: UUID = Path(
        ..., description="The unique identifier of the source connection"
    ),
    job_id: UUID = Path(..., description="The unique identifier of the sync job to cancel"),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.SourceConnectionJob:
    """Cancel a running sync job.

    <br/><br/>
    Sends a cancellation signal to stop an in-progress data synchronization.
    The job will complete its current operation and then terminate gracefully.
    Only jobs in 'created', 'pending', or 'in_progress' states can be cancelled.
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
    source_short_name: str = Path(
        ..., description="The source type identifier (e.g., 'google_drive', 'slack')"
    ),
    client_id: Optional[str] = Query(
        None, description="Optional custom OAuth client ID (for bring-your-own-credentials)"
    ),
) -> schemas.OAuth2AuthUrl:
    """Get the OAuth2 authorization URL for a source.

    <br/><br/>
    Generates the URL where users should be redirected to authorize Airweave
    to access their data. This is the first step in the OAuth flow for sources
    like Google Drive, Slack, or HubSpot.
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
    source_short_name: str = Path(
        ..., description="The source type identifier (e.g., 'google_drive', 'slack')"
    ),
    code: str = Query(..., description="The authorization code received from the OAuth callback"),
    credential_name: Optional[str] = Body(
        None, description="Custom name for the stored credential"
    ),
    credential_description: Optional[str] = Body(
        None, description="Description to help identify this credential"
    ),
    client_id: Optional[str] = Body(
        None, description="OAuth client ID (required for bring-your-own-credentials)"
    ),
    client_secret: Optional[str] = Body(
        None, description="OAuth client secret (required for bring-your-own-credentials)"
    ),
    auth_context: AuthContext = Depends(deps.get_auth_context),
) -> schemas.IntegrationCredentialInDB:
    """Exchange an OAuth2 authorization code for access credentials.

    <br/><br/>
    After users authorize Airweave through the OAuth consent screen, use this endpoint
    to exchange the temporary authorization code for permanent access credentials.
    The credentials are securely encrypted and stored for future syncs.
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
