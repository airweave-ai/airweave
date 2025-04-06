"""The API module that contains the endpoints for connections."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.core import credentials
from airweave.core.constants.native_connections import NATIVE_WEAVIATE_UUID
from airweave.core.logging import logger
from airweave.core.shared_models import SyncStatus
from airweave.db.session import get_db_context
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.integration_credential import IntegrationType
from airweave.platform.auth.schemas import AuthType
from airweave.platform.auth.services import oauth2_service
from airweave.platform.auth.settings import integration_settings
from airweave.platform.locator import resource_locator
from airweave.platform.sync.service import sync_service
from airweave.schemas.connection import ConnectionCreate, ConnectionStatus

router = APIRouter()


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
    connection = await crud.connection.get(db, id=connection_id, current_user=user)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    return connection


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
    connections = await crud.connection.get_all_for_user(db, current_user=user)
    return connections


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
    connections = await crud.connection.get_by_integration_type(
        db, integration_type=integration_type, organization_id=user.organization_id
    )

    return connections


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
    async with UnitOfWork(db) as uow:
        # Get the integration based on type
        integration = None
        if integration_type == IntegrationType.SOURCE:
            integration = await crud.source.get_by_short_name(uow.session, short_name)
        elif integration_type == IntegrationType.DESTINATION:
            integration = await crud.destination.get_by_short_name(uow.session, short_name)
        elif integration_type == IntegrationType.EMBEDDING_MODEL:
            integration = await crud.embedding_model.get_by_short_name(uow.session, short_name)

        if not integration:
            raise HTTPException(
                status_code=400,
                detail=f"{integration_type} with short_name '{short_name}' does not exist",
            )

        # For AuthType.none sources, we don't need integration credentials
        if integration.auth_type == AuthType.none or integration.auth_type is None:
            # Create connection directly without integration credential
            connection_data = {
                "name": name if name else f"Connection to {integration.name}",
                "integration_type": integration_type,
                "status": ConnectionStatus.ACTIVE,
                "integration_credential_id": None,  # No credential needed
                "short_name": short_name,
            }

            connection_in = ConnectionCreate(**connection_data)
            connection = await crud.connection.create(
                uow.session, obj_in=connection_in, current_user=user, uow=uow
            )

            await uow.commit()
            await uow.session.refresh(connection)

            return connection

        # For config_class auth type, validate config fields
        elif integration.auth_type == AuthType.config_class:
            if not integration.auth_config_class:
                raise HTTPException(
                    status_code=400,
                    detail=f"Integration {integration.name} does not have an auth config class",
                )
            # Create and validate auth config
            auth_config_class = resource_locator.get_auth_config(integration.auth_config_class)
            auth_config = auth_config_class(**config_fields)
            encrypted_creds = credentials.encrypt(auth_config.model_dump())
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Integration {integration.name} does not support config fields, "
                    "use the UI to connect"
                ),
            )

        # Create integration credential for authenticated sources
        integration_cred_in = schemas.IntegrationCredentialCreateEncrypted(
            name=f"{integration.name} - {user.email}",
            description=f"Credentials for {integration.name} - {user.email}",
            integration_short_name=integration.short_name,
            integration_type=integration_type,
            auth_type=integration.auth_type,
            encrypted_credentials=encrypted_creds,
            auth_config_class=integration.auth_config_class,
        )

        integration_cred = await crud.integration_credential.create(
            uow.session, obj_in=integration_cred_in, current_user=user, uow=uow
        )
        await uow.session.flush()

        # Create connection with appropriate ID field
        connection_data = {
            "name": name if name else f"Connection to {integration.name}",
            "integration_type": integration_type,
            "status": ConnectionStatus.ACTIVE,
            "integration_credential_id": integration_cred.id,
            "short_name": short_name,
        }

        connection_in = ConnectionCreate(**connection_data)
        connection = await crud.connection.create(
            uow.session, obj_in=connection_in, current_user=user, uow=uow
        )

        await uow.commit()
        await uow.session.refresh(connection)

        return connection


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
    connection = await crud.connection.get(db, id=connection_id, current_user=user)
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")

    integration_credential = await crud.integration_credential.get(
        db, id=connection.integration_credential_id, current_user=user
    )
    if not integration_credential:
        raise HTTPException(status_code=404, detail="Integration credential not found")

    decrypted_credentials = credentials.decrypt(integration_credential.encrypted_credentials)
    return decrypted_credentials


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
    # TODO: Implement data deletion logic, should be part of destination interface
    async with UnitOfWork(db) as uow:
        # Get connection
        connection = await crud.connection.get(uow.session, id=connection_id, current_user=user)

        if not connection:
            raise HTTPException(
                status_code=404,
                detail=f"No active connection found for '{connection_id}'",
            )

        _ = await crud.sync.remove_all_for_connection(
            uow.session, connection_id, current_user=user, uow=uow
        )
        # TODO: Implement data deletion logic, should be part of destination interface
        pass

        # Delete the connection and the integration credential
        connection = await crud.connection.remove(
            uow.session, id=connection_id, current_user=user, uow=uow
        )

        await crud.integration_credential.remove(
            uow.session, id=connection.integration_credential_id, current_user=user, uow=uow
        )

        await uow.commit()

        return connection


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
        connection_schema (schemas.Connection): The disconnected connection
    """
    async with UnitOfWork(db) as uow:
        connection = await crud.connection.get(uow.session, id=connection_id, current_user=user)
        if not connection:
            raise HTTPException(status_code=404, detail="Connection not found")
        if connection.integration_type != IntegrationType.SOURCE:
            raise HTTPException(status_code=400, detail="Connection is not a source")

        connection_schema = schemas.ConnectionUpdate.model_validate(
            connection, from_attributes=True
        )

        connection_schema.status = ConnectionStatus.INACTIVE
        connection = await crud.connection.update(
            uow.session, db_obj=connection, obj_in=connection_schema, current_user=user, uow=uow
        )
        connection_schema = schemas.Connection.model_validate(connection, from_attributes=True)

        syncs = await crud.sync.get_all_for_source_connection(
            uow.session, connection_id, current_user=user
        )
        for sync in syncs:
            sync.status = SyncStatus.INACTIVE
            sync_update_schema = schemas.SyncUpdate.model_validate(sync, from_attributes=True)
            await crud.sync.update(
                uow.session, db_obj=sync, obj_in=sync_update_schema, current_user=user, uow=uow
            )

        await uow.commit()

    return connection_schema


@router.put("/disconnect/destination/{connection_id}", response_model=schemas.Connection)
async def disconnect_destination_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    connection_id: UUID,
    user: schemas.User = Depends(deps.get_user),
) -> schemas.Connection:
    """Disconnect from a destination connection.

    Args:
    -----
        db (AsyncSession): The database session
        connection_id (UUID): The ID of the connection to disconnect
        user (schemas.User): The current user

    Returns:
    --------
        connection_schema (schemas.Connection): The disconnected connection
    """
    async with UnitOfWork(db) as uow:
        connection = await crud.connection.get(uow.session, id=connection_id, current_user=user)

        if not connection:
            raise HTTPException(status_code=404, detail="Connection not found")

        if connection.integration_type != IntegrationType.DESTINATION:
            raise HTTPException(status_code=400, detail="Connection is not a destination")

        connection_schema = schemas.ConnectionUpdate.model_validate(
            connection, from_attributes=True
        )

        connection_schema.status = ConnectionStatus.INACTIVE
        connection = await crud.connection.update(
            uow.session, db_obj=connection, obj_in=connection_schema, current_user=user, uow=uow
        )

        connection_schema = schemas.Connection.model_validate(connection, from_attributes=True)

        syncs = await crud.sync.get_all_for_destination_connection(
            uow.session, connection_id, current_user=user
        )
        for sync in syncs:
            sync.status = SyncStatus.INACTIVE
            sync_update_schema = schemas.SyncUpdate.model_validate(sync, from_attributes=True)
            await crud.sync.update(
                uow.session, db_obj=sync, obj_in=sync_update_schema, current_user=user, uow=uow
            )

        await uow.commit()

        return connection_schema


@router.get("/oauth2/source/auth_url")
async def get_oauth2_auth_url(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
    user: schemas.User = Depends(deps.get_user),
) -> str:
    """Get the OAuth2 authorization URL for a source.

    Args:
    -----
        db: The database session
        short_name: The short name of the source
        user: The current user
    """
    settings = integration_settings.get_by_short_name(short_name)
    if not settings:
        raise HTTPException(status_code=404, detail="Integration not found")

    if short_name == "trello":
        return oauth2_service.generate_auth_url_for_trello()

    if settings.auth_type not in [
        AuthType.oauth2,
        AuthType.oauth2_with_refresh,
        AuthType.oauth2_with_refresh_rotating,
    ]:
        raise HTTPException(status_code=400, detail="Integration does not support OAuth2")
    return oauth2_service.generate_auth_url(settings)


@router.post("/oauth2/source/code")
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
    try:
        return await oauth2_service.create_oauth2_connection(
            db=db,
            short_name=short_name,
            code=code,
            user=user,
        )
    except Exception as e:
        logger.error(f"Failed to exchange OAuth2 code: {e}")
        raise HTTPException(status_code=400, detail="Failed to exchange OAuth2 code") from e


@router.post("/oauth2/white-label/{white_label_id}/code")
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
    try:
        white_label = await crud.white_label.get(db, id=white_label_id, current_user=user)
        if not white_label:
            raise HTTPException(status_code=404, detail="White label integration not found")

        white_label_schema = schemas.WhiteLabel.model_validate(white_label, from_attributes=True)

        connection = await oauth2_service.create_oauth2_connection_for_whitelabel(
            db=db,
            white_label=white_label,
            code=code,
            user=user,
        )
        connection_schema = schemas.Connection.model_validate(connection, from_attributes=True)

        async with get_db_context() as db:
            async with UnitOfWork(db) as uow:
                # Create sync for the connection
                sync_in = schemas.SyncBase(
                    name=(
                        f"Sync for {connection_schema.name} from white label {white_label_schema.name}"
                    ),
                    source_connection_id=connection_schema.id,
                    destination_connection_ids=[NATIVE_WEAVIATE_UUID],
                    status=SyncStatus.ACTIVE,
                    white_label_id=white_label_schema.id,
                )
                sync_schema = await sync_service.create(db, sync_in, user, uow)
                sync_dag = await crud.sync_dag.get_by_sync_id(
                    db=db, sync_id=sync_schema.id, current_user=user
                )
                sync_job_create = schemas.SyncJobCreate(sync_id=sync_schema.id)
                sync_job = await crud.sync_job.create(
                    db, obj_in=sync_job_create, current_user=user, uow=uow
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

    except Exception as e:
        logger.error(f"Failed to exchange OAuth2 code for white label: {e}")
        raise HTTPException(status_code=400, detail="Failed to exchange OAuth2 code") from e


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
    try:
        white_label = await crud.white_label.get(
            db,
            id=white_label_id,
            current_user=user,
        )
        if not white_label:
            raise HTTPException(status_code=404, detail="White label integration not found")

        source = await crud.source.get_by_short_name(db, short_name=white_label.source_short_name)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        # Get the source settings since white label is based on a source
        settings = integration_settings.get_by_short_name(source.short_name)
        if not settings:
            raise HTTPException(status_code=404, detail="Integration settings not found")

        if settings.auth_type not in [
            AuthType.oauth2,
            AuthType.oauth2_with_refresh,
            AuthType.oauth2_with_refresh_rotating,
        ]:
            raise HTTPException(status_code=400, detail="Integration does not support OAuth2")

        # Generate auth URL using the white label's client ID and redirect URL
        return await oauth2_service.generate_auth_url_for_whitelabel(db, white_label)
    except Exception as e:
        logger.error(f"Failed to generate auth URL for white label: {e}")
        raise HTTPException(status_code=400, detail="Failed to generate auth URL") from e
