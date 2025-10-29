"""The API module that contains the endpoints for connections."""

from typing import Optional
from uuid import UUID

from fastapi import Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.rbac import require_org_role
from airweave.api.router import TrailingSlashRouter
from airweave.core.connection_service import connection_service
from airweave.models.integration_credential import IntegrationType

router = TrailingSlashRouter()


@router.get("/detail/{connection_id}", response_model=schemas.Connection)
async def get_connection(
    connection_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.Connection:
    """Get a specific connection.

    Args:
    -----
        connection_id: The ID of the connection to get.
        db: The database session.
        ctx: The current authentication context.

    Returns:
    -------
        schemas.Connection: The connection.
    """
    return await connection_service.get_connection(db, connection_id, ctx)


@router.get(
    "/list",
    response_model=list[schemas.Connection],
)
async def list_all_connected_integrations(
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> list[schemas.Connection]:
    """Get all active connections for the current user across all integration types.

    Args:
    -----
        db: The database session.
        ctx: The current authentication context.

    Returns:
    -------
        list[schemas.Connection]: The list of connections.
    """
    return await connection_service.get_all_connections(db, ctx)


@router.get(
    "/list/{integration_type}",
    response_model=list[schemas.Connection],
)
async def list_connected_integrations(
    integration_type: IntegrationType,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> list[schemas.Connection]:
    """Get all integrations of specified type connected to the current organization.

    Args:
    -----
        integration_type (IntegrationType): The type of integration to get connections for.
        db (AsyncSession): The database session.
        ctx (ApiContext): The current authentication context.

    Returns:
    -------
        list[schemas.Connection]: The list of connections.
    """
    return await connection_service.get_connections_by_type(db, integration_type, ctx)


@router.get("/credentials/{connection_id}", response_model=dict)
async def get_connection_credentials(
    connection_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
) -> dict:
    """Get the credentials for a connection.

    Args:
    -----
        connection_id (UUID): The ID of the connection to get credentials for
        db (AsyncSession): The database session
        ctx (ApiContext): The current authentication context

    Returns:
    -------
        decrypted_credentials (dict): The credentials for the connection
    """
    return await connection_service.get_connection_credentials(db, connection_id, ctx)


@router.delete("/delete/source/{connection_id}", response_model=schemas.Connection)
async def delete_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    connection_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.Connection:
    """Delete a connection.

    This operation requires admin or owner role within the organization.

    Deletes the connection and integration credential.

    Args:
    -----
        db (AsyncSession): The database session
        connection_id (UUID): The ID of the connection to delete
        ctx (ApiContext): The current authentication context

    Returns:
    --------
        connection (schemas.Connection): The deleted connection

    Raises:
    -------
        HTTPException: If user lacks admin privileges (403) or connection not found (404).
    """
    # Validate user has admin role
    require_org_role(ctx, min_role="admin")

    return await connection_service.delete_connection(db, connection_id, ctx)


@router.put("/disconnect/source/{connection_id}", response_model=schemas.Connection)
async def disconnect_source_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    connection_id: UUID,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.Connection:
    """Disconnect from a source connection.

    This operation requires admin or owner role within the organization.

    Args:
    -----
        db (AsyncSession): The database session
        connection_id (UUID): The ID of the connection to disconnect
        ctx (ApiContext): The current authentication context

    Returns:
    --------
        connection (schemas.Connection): The disconnected connection

    Raises:
    -------
        HTTPException: If user lacks admin privileges (403) or connection not found (404).
    """
    # Validate user has admin role
    require_org_role(ctx, min_role="admin")

    connection = await connection_service.disconnect_source(db, connection_id, ctx)
    # Ensure we return something that is compatible with the response_model
    return connection


@router.post(
    "/direct-token/slack",
    response_model=schemas.Connection,
)
async def connect_slack_with_token(
    *,
    db: AsyncSession = Depends(deps.get_db),
    token: str = Body(...),
    name: Optional[str] = Body(None),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.Connection:
    """Connect to Slack using a direct API token (for local development only).

    Args:
    -----
        db: The database session.
        token: The Slack API token.
        name: The name of the connection.
        ctx: The current authentication context.

    Returns:
    -------
        schemas.Connection: The connection.
    """
    return await connection_service.connect_with_direct_token(
        db, "slack", token, name, ctx, validate_token=True
    )


@router.post(
    "/credentials/{integration_type}/{short_name}", response_model=schemas.IntegrationCredentialInDB
)
async def create_integration_credential(
    *,
    db: AsyncSession = Depends(deps.get_db),
    integration_type: IntegrationType,
    short_name: str,
    credential_in: schemas.IntegrationCredentialRawCreate = Body(...),
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.IntegrationCredentialInDB:
    """Create integration credentials with validation.

    1. Takes auth_fields and validates them against the auth_config_class
    2. Encrypts and stores them in integration_credentials
    3. Returns the integration credential with ID

    Args:
        db: The database session
        integration_type: Type of integration (SOURCE, DESTINATION, etc.)
        short_name: Short name of the integration
        credential_in: The credential data with auth_fields
        ctx: The current authentication context

    Returns:
        The created integration credential

    Raises:
        HTTPException: If validation fails
    """
    return await connection_service.create_integration_credential(
        db, integration_type, short_name, credential_in, ctx
    )
