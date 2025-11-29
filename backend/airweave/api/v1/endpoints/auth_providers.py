"""Auth Provider endpoints for managing auth provider connections."""

from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter
from airweave.core import credentials
from airweave.core.logging import logger
from airweave.core.shared_models import ConnectionStatus, IntegrationType
from airweave.db.unit_of_work import UnitOfWork
from airweave.platform.auth.settings import AuthenticationMethod
from airweave.platform.configs._base import Fields
from airweave.platform.locator import resource_locator
from airweave.core.exceptions import PreSyncValidationException

router = TrailingSlashRouter()


async def _validate_auth_fields(
    db: AsyncSession, auth_provider_short_name: str, auth_fields: Optional[Dict[str, Any]]
) -> dict:
    """Validate auth fields based on auth type.

    Args:
        db: The database session
        auth_provider_short_name: The short name of the auth provider
        auth_fields: The auth fields to validate

    Returns:
        The validated auth fields as a dict

    Raises:
        HTTPException: If auth fields are invalid or not supported
    """
    # Get the auth provider info
    auth_provider = await crud.auth_provider.get_by_short_name(
        db, short_name=auth_provider_short_name
    )
    if not auth_provider:
        raise HTTPException(
            status_code=404, detail=f"Auth provider '{auth_provider_short_name}' not found"
        )

    # Check if auth_config_class is defined for the auth provider
    if not auth_provider.auth_config_class:
        raise HTTPException(
            status_code=422,
            detail=f"Auth provider {auth_provider.name} does not have an auth config defined.",
        )

    if auth_fields is None:
        raise HTTPException(
            status_code=422, detail=f"Auth provider {auth_provider.name} requires auth fields."
        )

    # Convert ConfigValues to dict if needed
    if hasattr(auth_fields, "model_dump"):
        auth_fields_dict = auth_fields.model_dump()
    else:
        auth_fields_dict = auth_fields

    # Create and validate auth config
    try:
        auth_config_class = resource_locator.get_auth_config(auth_provider.auth_config_class)
        auth_config = auth_config_class(**auth_fields_dict)
        return auth_config.model_dump()
    except Exception as e:
        logger.error(f"Failed to validate auth fields: {e}")

        # Check if it's a Pydantic validation error and format it nicely
        from pydantic import ValidationError

        if isinstance(e, ValidationError):
            # Extract the field names and error messages
            error_messages = []
            for error in e.errors():
                field = ".".join(str(loc) for loc in error.get("loc", []))
                msg = error.get("msg", "")
                error_messages.append(f"Field '{field}': {msg}")

            error_detail = (
                f"Invalid configuration for {auth_provider.auth_config_class}:\n"
                + "\n".join(error_messages)
            )
            raise HTTPException(
                status_code=422, detail=f"Invalid auth fields: {error_detail}"
            ) from e
        else:
            # For other types of errors
            raise HTTPException(status_code=422, detail=f"Invalid auth fields: {str(e)}") from e


async def _validate_auth_provider_credentials(
    db: AsyncSession,
    auth_provider_short_name: str,
    validated_auth_fields: dict,
    validated_provider_config: dict,
    ctx: ApiContext,
) -> None:
    """Validate that the auth provider connection actually works.

    Args:
        db: The database session
        auth_provider_short_name: The short name of the auth provider
        validated_auth_fields: The validated auth fields
        validated_provider_config: The validated provider config
        ctx: The API context

    Raises:
        HTTPException: If the connection validation fails
    """
    try:
        # First get the auth provider object from the database
        from airweave import crud

        auth_provider = await crud.auth_provider.get_by_short_name(
            db, short_name=auth_provider_short_name
        )
        if not auth_provider:
            raise HTTPException(
                status_code=404, detail=f"Auth provider not found: {auth_provider_short_name}"
            )

        # Get the auth provider class using the full auth provider object
        auth_provider_class = resource_locator.get_auth_provider(auth_provider)

        # Create a temporary instance with the provided credentials
        auth_provider_instance = await auth_provider_class.create(
            credentials=validated_auth_fields,
            config=validated_provider_config,
        )

        # Set the logger from context
        auth_provider_instance.set_logger(ctx.logger)

        # Validate the connection
        await auth_provider_instance.validate()

        ctx.logger.info(
            f"✅ Auth provider connection validation successful for {auth_provider_short_name}"
        )

    except HTTPException:
        # Re-raise HTTPException as-is (these come from the validation methods)
        raise
    except PreSyncValidationException as e:
        error_msg = f"Failed to validate {auth_provider_short_name} connection: {str(e)}"
        ctx.logger.error(error_msg, exc_info=True)
        raise
    except Exception as e:
        error_msg = f"Failed to validate {auth_provider_short_name} connection: {str(e)}"
        ctx.logger.error(f"❌ {error_msg}", exc_info=True)
        raise HTTPException(status_code=422, detail=error_msg) from e


@router.get("/list", response_model=List[schemas.AuthProvider])
async def list_auth_providers(
    *,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    skip: int = 0,
    limit: int = 100,
) -> List[schemas.AuthProvider]:
    """Get all available auth providers.

    Args:
    -----
        db: The database session
        ctx: The current authentication context
        skip: Number of auth providers to skip
        limit: Maximum number of auth providers to return

    Returns:
    --------
        List[schemas.AuthProvider]: List of available auth providers
    """
    auth_providers = await crud.auth_provider.get_multi(db, skip=skip, limit=limit)

    # Populate auth_fields for each auth provider
    result_providers = []
    for provider in auth_providers:
        try:
            provider_dict = {
                key: getattr(provider, key) for key in provider.__dict__ if not key.startswith("_")
            }

            # Skip if no auth config class
            if not provider.auth_config_class:
                ctx.logger.warning(f"Auth provider {provider.short_name} has no auth_config_class")
                result_providers.append(provider)
                continue

            # Get auth fields from auth config class
            auth_config_class = resource_locator.get_auth_config(provider.auth_config_class)
            auth_fields = Fields.from_config_class(auth_config_class)
            provider_dict["auth_fields"] = auth_fields

            # Get config fields from config class if it exists
            if provider.config_class:
                try:
                    config_class = resource_locator.get_config(provider.config_class)
                    config_fields = Fields.from_config_class(config_class)
                    provider_dict["config_fields"] = config_fields
                except Exception as e:
                    ctx.logger.error(
                        f"Error getting config fields for {provider.short_name}: {str(e)}"
                    )
                    # Still include the provider without config_fields
                    provider_dict["config_fields"] = None
            else:
                provider_dict["config_fields"] = None

            provider_model = schemas.AuthProvider.model_validate(provider_dict)
            result_providers.append(provider_model)

        except Exception as e:
            logger.error(f"Error processing auth provider {provider.short_name}: {str(e)}")
            # Still include the provider without auth_fields or config_fields
            result_providers.append(provider)

    return result_providers


@router.get("/connections/", response_model=List[schemas.AuthProviderConnection])
async def list_auth_provider_connections(
    *,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    skip: int = 0,
    limit: int = 100,
) -> List[schemas.AuthProviderConnection]:
    """Get all auth provider connections for the current organization.

    This endpoint returns all active auth provider connections that belong to the
    user's organization. While not enforced at the backend level, the frontend
    should typically ensure only one connection per auth provider type.

    Args:
    -----
        db: The database session
        ctx: The current authentication context
        skip: Number of connections to skip
        limit: Maximum number of connections to return

    Returns:
    --------
        List[schemas.AuthProviderConnection]: List of auth provider connections
    """
    # Get all connections with integration_type = AUTH_PROVIDER for the current organization
    connections = await crud.connection.get_by_integration_type(
        db,
        integration_type=IntegrationType.AUTH_PROVIDER,
        ctx=ctx,
    )

    # Apply skip and limit manually since get_by_integration_type doesn't support them
    connections = connections[skip : skip + limit]

    # Convert to AuthProviderConnection schema with masked client_id
    result = []
    for connection in connections:
        masked_client_id = await _get_masked_client_id(db, connection, ctx)
        result.append(
            schemas.AuthProviderConnection(
                id=connection.id,
                name=connection.name,
                readable_id=connection.readable_id,
                short_name=connection.short_name,
                description=connection.description,
                created_by_email=connection.created_by_email,
                modified_by_email=connection.modified_by_email,
                created_at=connection.created_at,
                modified_at=connection.modified_at,
                masked_client_id=masked_client_id,
            )
        )
    return result


@router.get("/connections/{readable_id}", response_model=schemas.AuthProviderConnection)
async def get_auth_provider_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    readable_id: str,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.AuthProviderConnection:
    """Get details of a specific auth provider connection.

    Args:
    -----
        db: The database session
        readable_id: The readable ID of the auth provider connection
        ctx: The current authentication context

    Returns:
    --------
        schemas.AuthProviderConnection: The auth provider connection details
    """
    # Find the connection by readable_id
    connection = await crud.connection.get_by_readable_id(db, readable_id=readable_id, ctx=ctx)

    if not connection:
        raise HTTPException(
            status_code=404,
            detail=f"Auth provider connection not found: {readable_id}",
        )

    # Verify it's an auth provider connection
    if connection.integration_type != IntegrationType.AUTH_PROVIDER:
        raise HTTPException(
            status_code=400,
            detail=f"Connection {readable_id} is not an auth provider connection",
        )

    # Get masked client_id if available
    masked_client_id = await _get_masked_client_id(db, connection, ctx)

    # Return as AuthProviderConnection schema
    return schemas.AuthProviderConnection(
        id=connection.id,
        name=connection.name,
        readable_id=connection.readable_id,
        short_name=connection.short_name,
        description=connection.description,
        created_by_email=connection.created_by_email,
        modified_by_email=connection.modified_by_email,
        created_at=connection.created_at,
        modified_at=connection.modified_at,
        masked_client_id=masked_client_id,
    )


@router.get("/detail/{short_name}", response_model=schemas.AuthProvider)
async def get_auth_provider(
    *,
    db: AsyncSession = Depends(deps.get_db),
    short_name: str,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.AuthProvider:
    """Get details of a specific auth provider.

    Args:
    -----
        db: The database session
        short_name: The short name of the auth provider
        ctx: The current authentication context

    Returns:
    --------
        schemas.AuthProvider: The auth provider details
    """
    auth_provider = await crud.auth_provider.get_by_short_name(db, short_name=short_name)
    if not auth_provider:
        raise HTTPException(
            status_code=404,
            detail=f"Auth provider not found: {short_name}",
        )

    # Populate auth_fields if auth_config_class exists
    if auth_provider.auth_config_class:
        try:
            auth_config_class = resource_locator.get_auth_config(auth_provider.auth_config_class)
            auth_fields = Fields.from_config_class(auth_config_class)

            # Create provider dict with auth_fields
            provider_dict = {
                **{
                    key: getattr(auth_provider, key)
                    for key in auth_provider.__dict__
                    if not key.startswith("_")
                },
                "auth_fields": auth_fields,
            }

            # Add config_fields if config_class exists
            if auth_provider.config_class:
                try:
                    config_class = resource_locator.get_config(auth_provider.config_class)
                    config_fields = Fields.from_config_class(config_class)
                    provider_dict["config_fields"] = config_fields
                except Exception as e:
                    logger.error(f"Error getting config fields for {short_name}: {str(e)}")
                    provider_dict["config_fields"] = None
            else:
                provider_dict["config_fields"] = None

            return schemas.AuthProvider.model_validate(provider_dict)
        except Exception as e:
            logger.error(f"Failed to get auth config for {short_name}: {str(e)}")
            # Return without auth_fields if there's an error

    return auth_provider


@router.post("/", response_model=schemas.AuthProviderConnection)
async def connect_auth_provider(
    *,
    db: AsyncSession = Depends(deps.get_db),
    auth_provider_connection_in: schemas.AuthProviderConnectionCreate,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.AuthProviderConnection:
    """Create a new auth provider connection with credentials.

    Args:
    -----
        db: The database session
        ctx: The current authentication context
        auth_provider_connection_in: The auth provider connection data

    Returns:
    --------
        schemas.AuthProviderConnection: The created connection
    """
    async with UnitOfWork(db) as uow:
        try:
            # 1. Validate auth provider exists
            auth_provider = await crud.auth_provider.get_by_short_name(
                uow.session, auth_provider_connection_in.short_name
            )
            if not auth_provider:
                raise HTTPException(
                    status_code=400,
                    detail=f"Auth provider not found: {auth_provider_connection_in.short_name}",
                )

            # 2. Validate auth fields
            validated_auth_fields = await _validate_auth_fields(
                uow.session,
                auth_provider_connection_in.short_name,
                auth_provider_connection_in.auth_fields,
            )

            # 3. Test the actual connection by creating a temporary auth provider instance
            await _validate_auth_provider_credentials(
                uow.session,
                auth_provider_connection_in.short_name,
                validated_auth_fields,
                {},  # Empty config - validation now works without it
                ctx,
            )

            # 5. Create integration credential with encrypted auth credentials
            integration_credential_data = schemas.IntegrationCredentialCreateEncrypted(
                name=f"{auth_provider_connection_in.name} Credentials",
                integration_short_name=auth_provider_connection_in.short_name,
                description=f"Credentials for {auth_provider_connection_in.name}",
                integration_type=IntegrationType.AUTH_PROVIDER,
                authentication_method=AuthenticationMethod.DIRECT,
                encrypted_credentials=credentials.encrypt(validated_auth_fields),
                auth_config_class=auth_provider.auth_config_class,
            )

            integration_credential = await crud.integration_credential.create(
                uow.session,
                obj_in=integration_credential_data,
                ctx=ctx,
                uow=uow,
            )
            await uow.session.flush()

            # 4. Create connection without config fields
            connection_data = schemas.ConnectionCreate(
                name=auth_provider_connection_in.name,
                readable_id=auth_provider_connection_in.readable_id,
                description=f"Auth provider connection for {auth_provider_connection_in.name}",
                integration_type=IntegrationType.AUTH_PROVIDER,
                status=ConnectionStatus.ACTIVE,
                integration_credential_id=integration_credential.id,
                short_name=auth_provider_connection_in.short_name,
            )

            connection = await crud.connection.create(
                uow.session,
                obj_in=connection_data,
                ctx=ctx,
                uow=uow,
            )
            await uow.session.flush()

            # 6. Get masked client_id if available
            masked_client_id = await _get_masked_client_id(uow.session, connection, ctx)

            # 7. Return response
            return schemas.AuthProviderConnection(
                id=connection.id,
                name=connection.name,
                readable_id=connection.readable_id,
                short_name=connection.short_name,
                description=connection.description,
                created_by_email=connection.created_by_email,
                modified_by_email=connection.modified_by_email,
                created_at=connection.created_at,
                modified_at=connection.modified_at,
                masked_client_id=masked_client_id,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to create auth provider connection: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to create auth provider connection: {str(e)}"
            ) from e


@router.delete("/{readable_id}", response_model=schemas.AuthProviderConnection)
async def delete_auth_provider_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    readable_id: str,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.AuthProviderConnection:
    """Delete an auth provider connection.

    This will cascade delete:
    - The associated integration credential
    - All source connections that were created using this auth provider
    - All connections and credentials associated with those source connections

    Args:
    -----
        db: The database session
        readable_id: The readable ID of the auth provider connection to delete
        ctx: The current authentication context

    Returns:
    --------
        schemas.AuthProviderConnection: The deleted connection information
    """
    # Find the connection by readable_id and integration_type
    connection = await crud.connection.get_by_readable_id(db, readable_id=readable_id, ctx=ctx)

    if not connection:
        raise HTTPException(
            status_code=404,
            detail=f"Auth provider connection not found: {readable_id}",
        )

    # Verify it's an auth provider connection
    if connection.integration_type != IntegrationType.AUTH_PROVIDER:
        raise HTTPException(
            status_code=400,
            detail=f"Connection {readable_id} is not an auth provider connection",
        )

    # Create response before deletion
    response = schemas.AuthProviderConnection(
        id=connection.id,
        name=connection.name,
        readable_id=connection.readable_id,
        short_name=connection.short_name,
        description=connection.description,
        created_by_email=connection.created_by_email,
        modified_by_email=connection.modified_by_email,
        created_at=connection.created_at,
        modified_at=connection.modified_at,
    )

    # Delete the connection - this will cascade to:
    # 1. integration_credential (via before_delete event in Connection model)
    # 2. source_connections that use this auth provider (via foreign key CASCADE)
    # 3. connections and syncs of those source_connections (via before_delete event in SourceConn)
    await crud.connection.remove(db, id=connection.id, ctx=ctx)

    return response


async def _update_auth_credentials(
    uow: UnitOfWork, connection: Any, auth_fields: dict, ctx: ApiContext
) -> None:
    """Update the encrypted credentials for a connection."""
    # Convert to dict if it's a Pydantic model
    if hasattr(auth_fields, "model_dump"):
        auth_fields_dict = auth_fields.model_dump()
    else:
        auth_fields_dict = auth_fields

    logger.info(f"[UPDATE AUTH CREDENTIALS] Auth fields to update: {list(auth_fields_dict.keys())}")

    validated_auth_fields = await _validate_auth_fields(
        uow.session, connection.short_name, auth_fields
    )
    logger.info("[UPDATE AUTH CREDENTIALS] Auth fields validated successfully")

    # TODO: Add connection validation once provider config is supported
    # For now, skip validation since we don't have the required config parameters
    logger.info(
        f"⚠️  [UPDATE AUTH CREDENTIALS] Skipping connection validation for {connection.short_name} "
        f"- provider config not yet supported"
    )

    if not connection.integration_credential_id:
        raise HTTPException(status_code=500, detail="Connection missing integration credential")

    integration_credential = await crud.integration_credential.get(
        uow.session, id=connection.integration_credential_id, ctx=ctx
    )

    if not integration_credential:
        raise HTTPException(status_code=404, detail="Integration credential not found")

    encrypted_credentials = credentials.encrypt(validated_auth_fields)

    integration_credential_update = schemas.IntegrationCredentialUpdate(
        encrypted_credentials=encrypted_credentials
    )

    await crud.integration_credential.update(
        uow.session,
        db_obj=integration_credential,
        obj_in=integration_credential_update,
        ctx=ctx,
        uow=uow,
    )
    await uow.session.flush()


async def _update_connection_fields(
    uow: UnitOfWork,
    connection: Any,
    update_data: schemas.AuthProviderConnectionUpdate,
    ctx: ApiContext,
    auth_fields_updated: bool,
) -> None:
    """Update connection fields and ensure timestamps are updated."""
    connection_update_data = {}
    if update_data.name is not None:
        connection_update_data["name"] = update_data.name
    if update_data.description is not None:
        connection_update_data["description"] = update_data.description

    # Update connection if we have fields to update
    if connection_update_data:
        connection_update = schemas.ConnectionUpdate(**connection_update_data)
        await crud.connection.update(
            uow.session,
            db_obj=connection,
            obj_in=connection_update,
            ctx=ctx,
            uow=uow,
        )

    # Ensure timestamps are updated when auth fields change
    if auth_fields_updated:
        from airweave.core.datetime_utils import utc_now_naive

        connection.modified_at = utc_now_naive()
        if ctx.has_user_context:
            connection.modified_by_email = ctx.tracking_email
        uow.session.add(connection)

    if connection_update_data or auth_fields_updated:
        await uow.session.flush()
        await uow.session.refresh(connection)


async def _get_masked_client_id(
    db: AsyncSession, connection: Any, ctx: ApiContext
) -> Optional[str]:
    """Get the masked client_id from the connection's credentials.

    Args:
        db: The database session
        connection: The connection object
        ctx: The API context

    Returns:
        Masked client_id string (e.g., "cli_abc...xyz") or None if not available
    """
    try:
        # Only process for OAuth providers that have client_id
        if not connection.integration_credential_id:
            return None

        # Get the credential
        credential = await crud.integration_credential.get(
            db, id=connection.integration_credential_id, ctx=ctx
        )

        if not credential:
            return None

        # Decrypt credentials
        decrypted = credentials.decrypt(credential.encrypted_credentials)

        # Check if client_id exists
        client_id = decrypted.get("client_id")
        if not client_id:
            return None

        # Mask the client_id - show first 7 and last 4 characters
        if len(client_id) <= 15:
            # Too short to mask effectively, show partial
            return f"{client_id[:4]}..."
        else:
            return f"{client_id[:7]}...{client_id[-4:]}"

    except Exception as e:
        logger.debug(f"Could not extract client_id for masking: {e}")
        return None


async def _validate_auth_provider_connection(
    db: AsyncSession, readable_id: str, ctx: ApiContext
) -> Any:
    """Validate and return auth provider connection."""
    connection = await crud.connection.get_by_readable_id(db, readable_id=readable_id, ctx=ctx)

    if not connection:
        raise HTTPException(
            status_code=404,
            detail=f"Auth provider connection not found: {readable_id}",
        )

    if connection.integration_type != IntegrationType.AUTH_PROVIDER:
        raise HTTPException(
            status_code=400,
            detail=f"Connection {readable_id} is not an auth provider connection",
        )

    return connection


@router.put("/{readable_id}", response_model=schemas.AuthProviderConnection)
async def update_auth_provider_connection(
    *,
    db: AsyncSession = Depends(deps.get_db),
    readable_id: str,
    auth_provider_connection_update: schemas.AuthProviderConnectionUpdate,
    ctx: ApiContext = Depends(deps.get_context),
) -> schemas.AuthProviderConnection:
    """Update an existing auth provider connection.

    This endpoint allows updating:
    - The connection name and description
    - The authentication credentials (which will be re-validated and re-encrypted)

    Args:
    -----
        db: The database session
        readable_id: The readable ID of the auth provider connection to update
        auth_provider_connection_update: The fields to update
        ctx: The current authentication context

    Returns:
    --------
        schemas.AuthProviderConnection: The updated connection information
    """
    async with UnitOfWork(db) as uow:
        try:
            # 1. Validate connection
            connection = await _validate_auth_provider_connection(uow.session, readable_id, ctx)

            # 2. Update auth fields if provided
            auth_fields_updated = auth_provider_connection_update.auth_fields is not None
            if auth_fields_updated:
                await _update_auth_credentials(
                    uow, connection, auth_provider_connection_update.auth_fields, ctx
                )

            # 3. Update connection fields
            await _update_connection_fields(
                uow, connection, auth_provider_connection_update, ctx, auth_fields_updated
            )

            # 4. Get masked client_id if available
            masked_client_id = await _get_masked_client_id(uow.session, connection, ctx)

            # 5. Return updated connection
            return schemas.AuthProviderConnection(
                id=connection.id,
                name=connection.name,
                readable_id=connection.readable_id,
                short_name=connection.short_name,
                description=connection.description,
                created_by_email=connection.created_by_email,
                modified_by_email=connection.modified_by_email,
                created_at=connection.created_at,
                modified_at=connection.modified_at,
                masked_client_id=masked_client_id,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to update auth provider connection: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Failed to update auth provider connection: {str(e)}"
            ) from e
