"""Service layer for managing connections to external services."""

from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core import credentials
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import logger
from airweave.core.shared_models import ConnectionStatus, SyncStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.integration_credential import IntegrationType
from airweave.schemas.connection import ConnectionCreate
from airweave.schemas.source_connection import AuthenticationMethod

connection_logger = logger.with_prefix("Connection Service: ").with_context(
    component="connection_service"
)


class ConnectionService:
    """Service for managing connections to external services.

    This service encapsulates all the connection-related operations, including:
    - Creating connections with different authentication types
    - Validating connections
    - Deleting connections
    - Managing connection status (connect/disconnect)
    """

    async def get_connection(
        self, db: AsyncSession, connection_id: UUID, ctx: ApiContext
    ) -> schemas.Connection:
        """Get a specific connection by ID.

        Args:
            db: The database session
            connection_id: The ID of the connection to retrieve
            ctx: The API context

        Returns:
            The connection

        Raises:
            NotFoundException: If the connection is not found
        """
        connection = await crud.connection.get(db, id=connection_id, ctx=ctx)
        if not connection:
            raise NotFoundException("Connection not found")
        return connection

    async def get_all_connections(
        self, db: AsyncSession, ctx: ApiContext
    ) -> list[schemas.Connection]:
        """Get all connections for the current user.

        Args:
            db: The database session
            ctx: The API context

        Returns:
            A list of connections
        """
        return await crud.connection.get_multi(db, ctx=ctx)

    async def get_connections_by_type(
        self, db: AsyncSession, integration_type: IntegrationType, user: schemas.User
    ) -> list[schemas.Connection]:
        """Get connections by integration type.

        Args:
            db: The database session
            integration_type: The type of integration
            user: The current user

        Returns:
            A list of connections
        """
        return await crud.connection.get_by_integration_type(
            db, integration_type=integration_type, organization_id=user.organization_id
        )

    async def connect_with_direct_token(
        self,
        db: AsyncSession,
        short_name: str,
        token: str,
        name: Optional[str],
        user: schemas.User,
        validate_token: bool = True,
    ) -> schemas.Connection:
        """Connect using a direct token (for local development).

        Args:
            db: The database session
            short_name: The short name of the integration
            token: The direct token
            name: The name of the connection
            user: The current user
            validate_token: Whether to validate the token

        Returns:
            The created connection

        Raises:
            HTTPException: If not in local development mode or validation fails
        """
        if not settings.LOCAL_DEVELOPMENT:
            raise HTTPException(
                status_code=403,
                detail="Direct token connection is only allowed in local development mode",
            )

        connection_name = name if name else f"Connection to {short_name.capitalize()}"

        # Service-specific token validation
        if validate_token:
            if short_name == "slack":
                connection_name = await self._validate_slack_token(token, name)

        async with UnitOfWork(db) as uow:
            # Get the integration
            source = await crud.source.get_by_short_name(uow.session, short_name)
            if not source:
                raise HTTPException(status_code=404, detail=f"{short_name} source not found")

            # Create integration credential for the token
            encrypted_creds = credentials.encrypt({"access_token": token})
            connection = await self._create_connection_with_credential(
                uow=uow,
                integration_type=IntegrationType.SOURCE,
                short_name=short_name,
                name=connection_name,
                integration_name=source.name,
                authentication_method=AuthenticationMethod.OAUTH_TOKEN,
                oauth_type=getattr(source, "oauth_type", None),
                encrypted_credentials=encrypted_creds,
                auth_config_class=None,
            )

            await uow.commit()
            await uow.session.refresh(connection)
            return connection

    async def delete_connection(
        self, db: AsyncSession, connection_id: UUID, ctx: ApiContext
    ) -> schemas.Connection:
        """Delete a connection and its integration credential.

        Args:
            db: The database session
            connection_id: The ID of the connection to delete
            ctx: The API context

        Returns:
            The deleted connection

        Raises:
            NotFoundException: If the connection is not found
        """
        async with UnitOfWork(db) as uow:
            # Get connection
            connection = await crud.connection.get(uow.session, id=connection_id, ctx=ctx)
            if not connection:
                raise NotFoundException(f"No active connection found for '{connection_id}'")

            # Remove all syncs for this connection
            await crud.sync.remove_all_for_connection(uow.session, connection_id, ctx=ctx, uow=uow)

            # Delete the connection
            connection = await crud.connection.remove(
                uow.session, id=connection_id, ctx=ctx, uow=uow
            )

            # Delete the integration credential if it exists
            if connection.integration_credential_id:
                await crud.integration_credential.remove(
                    uow.session,
                    id=connection.integration_credential_id,
                    ctx=ctx,
                    uow=uow,
                )

            await uow.commit()
            return connection

    async def disconnect_source(
        self, db: AsyncSession, connection_id: UUID, ctx: ApiContext
    ) -> schemas.Connection:
        """Disconnect from a source connection (set to inactive).

        Args:
            db: The database session
            connection_id: The ID of the source connection
            ctx: The API context

        Returns:
            The updated connection

        Raises:
            NotFoundException: If the connection is not found
            HTTPException: If the connection is not a source
        """
        async with UnitOfWork(db) as uow:
            connection = await crud.connection.get(uow.session, id=connection_id, ctx=ctx)
            if not connection:
                raise NotFoundException("Connection not found")

            if connection.integration_type != IntegrationType.SOURCE:
                raise HTTPException(status_code=400, detail="Connection is not a source")

            connection.status = ConnectionStatus.INACTIVE
            connection_update = schemas.ConnectionUpdate.model_validate(
                connection, from_attributes=True
            )
            await crud.connection.update(
                uow.session,
                db_obj=connection,
                obj_in=connection_update,
                ctx=ctx,
                uow=uow,
            )

            # Also set all syncs using this source to inactive
            syncs = await crud.sync.get_all_for_source_connection(
                uow.session, connection_id, ctx=ctx
            )

            for sync in syncs:
                sync.status = SyncStatus.INACTIVE
                sync_update = schemas.SyncUpdate.model_validate(sync, from_attributes=True)
                await crud.sync.update(
                    uow.session,
                    db_obj=sync,
                    obj_in=sync_update,
                    ctx=ctx,
                    uow=uow,
                )
            connection = schemas.Connection.model_validate(connection, from_attributes=True)
            await uow.commit()
            return connection

    async def get_connection_credentials(
        self, db: AsyncSession, connection_id: UUID, ctx: ApiContext
    ) -> Dict[str, Any]:
        """Get decrypted credentials for a connection.

        Args:
            db: The database session
            connection_id: The ID of the connection
            ctx: The API context

        Returns:
            The decrypted credentials

        Raises:
            NotFoundException: If the connection or credential is not found
        """
        connection = await crud.connection.get(db, id=connection_id, ctx=ctx)
        if not connection:
            raise NotFoundException("Connection not found")

        if not connection.integration_credential_id:
            raise NotFoundException("Connection has no integration credential")

        integration_credential = await crud.integration_credential.get(
            db, id=connection.integration_credential_id, ctx=ctx
        )

        if not integration_credential:
            raise NotFoundException("Integration credential not found")

    async def _create_connection_with_credential(
        self,
        uow: UnitOfWork,
        integration_type: IntegrationType,
        short_name: str,
        name: Optional[str],
        integration_name: str,
        authentication_method: AuthenticationMethod,
        oauth_type: Optional[str],
        encrypted_credentials: str,
        auth_config_class: Optional[str],
        ctx: ApiContext,
    ) -> schemas.Connection:
        """Create a connection with credentials.

        Args:
            uow: The unit of work
            integration_type: The type of integration
            short_name: The short name of the integration
            name: The name of the connection
            integration_name: The name of the integration
            authentication_method: The authentication method
            oauth_type: The OAuth type (for OAuth methods)
            encrypted_credentials: The encrypted credentials
            auth_config_class: The auth config class name
            ctx: The API context

        Returns:
            The created connection
        """
        # Create integration credential
        integration_cred_in = schemas.IntegrationCredentialCreateEncrypted(
            name=f"{integration_name} - {ctx.organization.id}",
            description=f"Credentials for {integration_name} - {ctx.organization.id}",
            integration_short_name=short_name,
            integration_type=integration_type,
            authentication_method=authentication_method,
            oauth_type=oauth_type,
            encrypted_credentials=encrypted_credentials,
            auth_config_class=auth_config_class,
        )

        integration_cred = await crud.integration_credential.create(
            uow.session, obj_in=integration_cred_in, ctx=ctx, uow=uow
        )
        await uow.session.flush()

        # Create connection
        connection_data = {
            "name": name if name else f"Connection to {integration_name}",
            "integration_type": integration_type,
            "status": ConnectionStatus.ACTIVE,
            "integration_credential_id": integration_cred.id,
            "short_name": short_name,
        }

        connection_in = ConnectionCreate(**connection_data)
        return await crud.connection.create(uow.session, obj_in=connection_in, ctx=ctx, uow=uow)

    async def _validate_slack_token(self, token: str, name: Optional[str]) -> str:
        """Validate a Slack token by making a test API call.

        Args:
            token: The Slack token to validate
            name: The user-provided connection name

        Returns:
            The connection name (possibly enriched with team info)

        Raises:
            HTTPException: If the token is invalid
        """
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                }
                response = await client.get("https://slack.com/api/auth.test", headers=headers)
                response.raise_for_status()
                data = response.json()

                if not data.get("ok", False):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid Slack token: {data.get('error', 'Unknown error')}",
                    )

                # Get the team name for a better connection name if not provided
                team_name = data.get("team", "Slack")
                return name if name else f"{team_name} Direct Token"
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to verify Slack token: {str(e)}"
            ) from e

    def _supports_oauth2(self, auth_method: AuthenticationMethod) -> bool:
        """Check if the authentication method supports OAuth2."""
        return auth_method in (
            AuthenticationMethod.OAUTH_BROWSER,
            AuthenticationMethod.OAUTH_TOKEN,
            AuthenticationMethod.OAUTH_BYOC,
        )

    async def create_integration_credential(  # noqa: C901
        self,
        db: AsyncSession,
        integration_type: IntegrationType,
        short_name: str,
        credential_in: schemas.IntegrationCredentialRawCreate,
        ctx: ApiContext,
    ) -> schemas.IntegrationCredentialInDB:
        """Create an integration credential with validation.

        Args:
            db: The database session
            integration_type: Type of integration
            short_name: Short name of the integration
            credential_in: The credential data with auth fields
            ctx: The API context

        Returns:
            The created integration credential with ID

        Raises:
            HTTPException: If validation fails or integration not found
        """
        # Get the integration based on type
        integration = None
        auth_config_class = None

        if integration_type == IntegrationType.SOURCE:
            integration = await crud.source.get_by_short_name(db, short_name=short_name)
            if integration:
                auth_config_class = integration.auth_config_class
        elif integration_type == IntegrationType.DESTINATION:
            integration = await crud.destination.get_by_short_name(db, short_name=short_name)
            if integration:
                auth_config_class = integration.auth_config_class
        elif integration_type == IntegrationType.EMBEDDING_MODEL:
            integration = await crud.embedding_model.get_by_short_name(db, short_name=short_name)
            if integration:
                auth_config_class = integration.auth_config_class

        if not integration:
            raise HTTPException(
                status_code=404, detail=f"Integration not found: {integration_type} {short_name}"
            )

        # Check if auth config class is defined
        BASE_ERROR_MESSAGE = (
            f"See https://docs.airweave.ai/{short_name}#authentication for more information."
        )

        if not auth_config_class:
            error_msg = (
                f"{integration_type} {short_name} does not have an auth configuration defined."
            )
            raise HTTPException(
                status_code=422,
                detail=error_msg + BASE_ERROR_MESSAGE,
            )

        # Validate auth fields
        validated_auth_fields = None
        try:
            from airweave.platform.locator import resource_locator

            auth_config_class_obj = resource_locator.get_auth_config(auth_config_class)
            auth_config = auth_config_class_obj(**credential_in.auth_fields)
            validated_auth_fields = auth_config.model_dump()
        except Exception as e:
            connection_logger.error(f"Failed to validate auth fields: {e}")
            self._handle_validation_error(e, auth_config_class, BASE_ERROR_MESSAGE)

        # Encrypt the validated auth fields
        encrypted_credentials = credentials.encrypt(validated_auth_fields)

        # Determine authentication method (for non-sources, it's always DIRECT)
        authentication_method = AuthenticationMethod.DIRECT
        oauth_type = None

        if integration_type == IntegrationType.SOURCE:
            # For sources, we could check auth_methods, but for now default to DIRECT
            # This would need to be passed in or determined from the credential_in
            authentication_method = AuthenticationMethod.DIRECT
            oauth_type = getattr(integration, "oauth_type", None)

        # Create the integration credential
        return await self._create_credential_in_db(
            db,
            credential_in,
            integration,
            integration_type,
            short_name,
            authentication_method,
            oauth_type,
            encrypted_credentials,
            auth_config_class,
            ctx,
        )

    def _handle_validation_error(self, error, auth_config_class, base_error_message):
        """Handle validation errors for auth fields."""
        from pydantic import ValidationError

        if isinstance(error, ValidationError):
            # Extract the field names and error messages
            error_messages = []
            for err in error.errors():
                field = ".".join(str(loc) for loc in err.get("loc", []))
                msg = err.get("msg", "")
                error_messages.append(f"Field '{field}': {msg}")

            error_detail = f"Invalid configuration for {auth_config_class}:\n" + "\n".join(
                error_messages
            )
            raise HTTPException(
                status_code=422,
                detail=f"Invalid auth fields: {error_detail}. " + base_error_message,
            ) from error
        else:
            # For other types of errors
            raise HTTPException(
                status_code=422,
                detail=f"Invalid auth fields: {str(error)}. " + base_error_message,
            ) from error

    async def _create_credential_in_db(
        self,
        db,
        credential_in,
        integration,
        integration_type,
        short_name,
        authentication_method,
        oauth_type,
        encrypted_credentials,
        auth_config_class,
        ctx,
    ):
        """Create the integration credential in the database."""
        async with UnitOfWork(db) as uow:
            integration_cred_in = schemas.IntegrationCredentialCreateEncrypted(
                name=credential_in.name,
                description=credential_in.description
                or f"Credentials for {integration.name} - {ctx.organization.id}",
                integration_short_name=short_name,
                integration_type=integration_type,
                authentication_method=authentication_method,
                oauth_type=oauth_type,
                encrypted_credentials=encrypted_credentials,
                auth_config_class=auth_config_class,
            )

            integration_credential = await crud.integration_credential.create(
                uow.session, obj_in=integration_cred_in, ctx=ctx, uow=uow
            )

            await uow.commit()
            await uow.session.refresh(integration_credential)

            # Get the schema model from the database object and return
            return schemas.IntegrationCredentialInDB.model_validate(
                integration_credential, from_attributes=True
            )


connection_service = ConnectionService()
