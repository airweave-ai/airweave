"""The API module that contains the endpoints for connections."""

from typing import Optional
from uuid import UUID

from fastapi import BackgroundTasks, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.router import TrailingSlashRouter
from airweave.core.connection_service import connection_service
from airweave.core.constants.native_connections import NATIVE_QDRANT_UUID
from airweave.core.shared_models import SyncStatus
from airweave.core.sync_service import sync_service
from airweave.db.session import get_db_context
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.integration_credential import IntegrationType

router = TrailingSlashRouter()


@router.get("/detail/{connection_id}", response_model=schemas.Connection)
async def get_connection(
    connection_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Connection:
    """Get a specific connection.

    Args:
    -----
        connection_id: The ID of the connection to get.
        db: The database session.
        user: The current user.

    Returns:
    -------
        schemas.Connection: The connection.
    """
    return await connection_service.get_connection(db, connection_id, user)


@router.get(
    "/list",
    response_model=list[schemas.Connection],
)
async def list_all_connected_integrations(
    db: AsyncSession = Depends(deps.get_db),
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.Connection]:
    """Get all active connections for the current user across all integration types.

    Args:
    -----
        db: The database session.
        user: The current user.

    Returns:
    -------
        list[schemas.Connection]: The list of connections.
    """
    return await connection_service.get_all_connections(db, user)


@router.get(
    "/list/{integration_type}",
    response_model=list[schemas.Connection],
)
async def list_connected_integrations(
    integration_type: IntegrationType,
    db: AsyncSession = Depends(deps.get_db),
    user: schemas.User = Depends(deps.get_user),
) -> list[schemas.Connection]:
    """Get all integrations of specified type connected to the current user.

    Args:
    -----
        integration_type (IntegrationType): The type of integration to get connections for.
        db (AsyncSession): The database session.
        user (schemas.User): The current user.

    Returns:
    -------
        list[schemas.Connection]: The list of connections.
    """
    return await connection_service.get_connections_by_type(db, integration_type, user)


@router.post(
    "/connect/{integration_type}/{short_name}",
    response_model=schemas.Connection,
)
async def connect_integration(
    *,
    db: AsyncSession = Depends(deps.get_db),
    integration_type: IntegrationType,
    short_name: str,
    name: Optional[str] = Body(default=None),
    config_fields: dict = Body(..., exclude={"name"}),
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Connection:
    """Connect to a source, destination, or embedding model.

    Expects a POST body with:
    ```json
    {
        "name": "required connection name",
        ... other config fields specific to the integration type ...
    }
    ```

    Args:
    -----
        db: The database session.
        integration_type: The type of integration to connect to.
        short_name: The short name of the integration to connect to.
        name: The name of the connection.
        config_fields: The config fields for the integration.
        user: The current user.

    Returns:
    -------
        schemas.Connection: The connection.
    """
    return await connection_service.connect_with_config(
        db, integration_type, short_name, name, config_fields, user
    )


@router.get("/credentials/{connection_id}", response_model=dict)
async def get_connection_credentials(
    connection_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    user: schemas.User = Depends(deps.get_user),
) -> dict:
    """Get the credentials for a connection.

    Args:
    -----
        connection_id (UUID): The ID of the connection to get credentials for
        db (AsyncSession): The database session
        user (schemas.User): The current user

    Returns:
    -------
        decrypted_credentials (dict): The credentials for the connection
    """
    return await connection_service.get_connection_credentials(db, connection_id, user)


@router.delete("/delete/source/{connection_id}", response_model=schemas.Connection)
async def delete_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    connection_id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Connection:
    """Delete a connection.

    Deletes the connection and integration credential.

    Args:
    -----
        db (AsyncSession): The database session
        connection_id (UUID): The ID of the connection to delete
        user (schemas.User): The current user

    Returns:
    --------
        connection (schemas.Connection): The deleted connection
    """
    return await connection_service.delete_connection(db, connection_id, user)


@router.put("/disconnect/source/{connection_id}", response_model=schemas.Connection)
async def disconnect_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    connection_id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Connection:
    """Disconnect from a source connection.

    Args:
    -----
        db (AsyncSession): The database session
        connection_id (UUID): The ID of the connection to disconnect
        user (schemas.User): The current user

    Returns:
    --------
        connection (schemas.Connection): The disconnected connection
    """
    connection = await connection_service.disconnect_source(db, connection_id, user)
    # Ensure we return something that is compatible with the response_model
    return connection


@router.get("/oauth2/source/auth_url")
async def get_oauth2_auth_url(
    *,
    short_name: str,
) -> str:
    """Get the OAuth2 authorization URL for a source.

    Args:
    -----
        short_name: The short name of the source
    """
    return await connection_service.get_oauth2_auth_url(short_name)


@router.post("/oauth2/source/code", response_model=schemas.Connection)
async def send_oauth2_code(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str = Body(...),
    code: str = Body(...),
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Connection:
    """Send the OAuth2 authorization code for a source.

    This will:
    1. Get the OAuth2 settings for the source
    2. Exchange the authorization code for a token
    3. Create an integration credential with the token

    Args:
    -----
        db: The database session
        short_name: The short name of the source
        code: The authorization code
        user: The current user

    Returns:
    --------
        connection (schemas.Connection): The created connection
    """
    return await connection_service.connect_with_oauth2_code(db, short_name, code, user)


@router.post("/oauth2/white-label/{white_label_id}/code", response_model=schemas.Connection)
async def send_oauth2_white_label_code(
    *,
    db: AsyncSession = Depends(deps.get_db),
    white_label_id: UUID,
    code: str = Body(...),
    user: schemas.User = Depends(deps.get_user),
    background_tasks: BackgroundTasks,
) -> schemas.Connection:
    """Exchange the OAuth2 authorization code for a white label integration.

    Args:
    -----
        db: The database session
        white_label_id: The ID of the white label integration
        code: The authorization code
        user: The current user
        background_tasks: The background tasks

    Returns:
    --------
        connection (schemas.Connection): The created connection
    """
    connection = await connection_service.connect_with_white_label_oauth2_code(
        db, white_label_id, code, user
    )

    # Create and run sync for the connection
    async with get_db_context() as sync_db:
        async with UnitOfWork(sync_db) as uow:
            white_label = await crud.white_label.get(sync_db, id=white_label_id, current_user=user)

            if not white_label:
                raise HTTPException(status_code=404, detail="White label integration not found")

            white_label_schema = schemas.WhiteLabel.model_validate(
                white_label, from_attributes=True
            )

            # Create sync for the connection
            sync_in = schemas.SyncBase(
                name=f"Sync for {connection.name} from white label {white_label_schema.name}",
                source_connection_id=connection.id,
                destination_connection_ids=[NATIVE_QDRANT_UUID],
                status=SyncStatus.ACTIVE,
                white_label_id=white_label_schema.id,
            )

            sync_schema = await sync_service.create(sync_db, sync_in, user, uow)
            sync_dag = await crud.sync_dag.get_by_sync_id(
                db=sync_db, sync_id=sync_schema.id, current_user=user
            )

            sync_job_create = schemas.SyncJobCreate(sync_id=sync_schema.id)
            sync_job = await crud.sync_job.create(
                sync_db, obj_in=sync_job_create, current_user=user, uow=uow
            )

            await uow.commit()
            await uow.session.refresh(sync_job)
            await uow.session.refresh(sync_dag)

            # Add background task to run the sync
            sync_job_schema = schemas.SyncJob.model_validate(sync_job)
            sync_dag_schema = schemas.SyncDag.model_validate(sync_dag)
            background_tasks.add_task(
                sync_service.run,
                sync_schema,
                sync_job_schema,
                sync_dag_schema,
                user,
            )

    return connection


@router.get("/oauth2/white-label/{white_label_id}/auth_url")
async def get_oauth2_white_label_auth_url(
    *,
    db: AsyncSession = Depends(deps.get_db),
    white_label_id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> str:
    """Get the OAuth2 authorization URL for a white label integration.

    Args:
    -----
        db: The database session
        white_label_id: The ID of the white label integration
        user: The current user

    Returns:
    --------
        str: The OAuth2 authorization URL
    """
    return await connection_service.get_white_label_oauth2_auth_url(db, white_label_id, user)


@router.post(
    "/direct-token/slack",
    response_model=schemas.Connection,
)
async def connect_slack_with_token(
    *,
    db: AsyncSession = Depends(deps.get_db),
    token: str = Body(...),
    name: Optional[str] = Body(None),
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Connection:
    """Connect to Slack using a direct API token (for local development only).

    Args:
    -----
        db: The database session.
        token: The Slack API token.
        name: The name of the connection.
        user: The current user.

    Returns:
    -------
        schemas.Connection: The connection.
    """
    return await connection_service.connect_with_direct_token(
        db, "slack", token, name, user, validate_token=True
    )
