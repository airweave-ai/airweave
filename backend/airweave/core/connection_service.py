"""Service layer for managing connections to external services."""

from typing import Any, Dict, Optional
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core import credentials
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import logger
from airweave.core.shared_models import ConnectionStatus, SyncStatus
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.integration_credential import IntegrationType
from airweave.platform.auth.schemas import AuthType
from airweave.schemas.connection import ConnectionCreate

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
        self, db: AsyncSession, connection_id: UUID, user: schemas.User
    ) -> schemas.Connection:
        """Get a specific connection by ID.

        Args:
            db: The database session
            connection_id: The ID of the connection to retrieve
            user: The current user

        Returns:
            The connection

        Raises:
            NotFoundException: If the connection is not found
        """
        connection = await crud.connection.get(db, id=connection_id, current_user=user)
        if not connection:
            raise NotFoundException("Connection not found")
        return connection

    async def get_all_connections(
        self, db: AsyncSession, user: schemas.User
    ) -> list[schemas.Connection]:
        """Get all connections for the current user.

        Args:
            db: The database session
            user: The current user

        Returns:
            A list of connections
        """
        return await crud.connection.get_all_for_user(db, current_user=user)

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
                auth_type=AuthType.oauth2,  # We store it as OAuth2 for compatibility
                encrypted_credentials=encrypted_creds,
                auth_config_class=None,
                user=user,
            )

            await uow.commit()
            await uow.session.refresh(connection)
            return connection

    async def delete_connection(
        self, db: AsyncSession, connection_id: UUID, user: schemas.User
    ) -> schemas.Connection:
        """Delete a connection and its integration credential.

        Args:
            db: The database session
            connection_id: The ID of the connection to delete
            user: The current user

        Returns:
            The deleted connection

        Raises:
            NotFoundException: If the connection is not found
        """
        async with UnitOfWork(db) as uow:
            # Get connection
            connection = await crud.connection.get(uow.session, id=connection_id, current_user=user)
            if not connection:
                raise NotFoundException(f"No active connection found for '{connection_id}'")

            # Remove all syncs for this connection
            await crud.sync.remove_all_for_connection(
                uow.session, connection_id, current_user=user, uow=uow
            )

            # Delete the connection
            connection = await crud.connection.remove(
                uow.session, id=connection_id, current_user=user, uow=uow
            )

            # Delete the integration credential if it exists
            if connection.integration_credential_id:
                await crud.integration_credential.remove(
                    uow.session, id=connection.integration_credential_id, current_user=user, uow=uow
                )

            await uow.commit()
            return connection

    async def disconnect_source(
        self, db: AsyncSession, connection_id: UUID, user: schemas.User
    ) -> schemas.Connection:
        """Disconnect from a source connection (set to inactive).

        Args:
            db: The database session
            connection_id: The ID of the source connection
            user: The current user

        Returns:
            The updated connection

        Raises:
            NotFoundException: If the connection is not found
            HTTPException: If the connection is not a source
        """
        async with UnitOfWork(db) as uow:
            connection = await crud.connection.get(uow.session, id=connection_id, current_user=user)
            if not connection:
                raise NotFoundException("Connection not found")

            if connection.integration_type != IntegrationType.SOURCE:
                raise HTTPException(status_code=400, detail="Connection is not a source")

            connection.status = ConnectionStatus.INACTIVE
            connection_update = schemas.ConnectionUpdate.model_validate(
                connection, from_attributes=True
            )
            await crud.connection.update(
                uow.session, db_obj=connection, obj_in=connection_update, current_user=user, uow=uow
            )

            # Also set all syncs using this source to inactive
            syncs = await crud.sync.get_all_for_source_connection(
                uow.session, connection_id, current_user=user
            )

            for sync in syncs:
                sync.status = SyncStatus.INACTIVE
                sync_update = schemas.SyncUpdate.model_validate(sync, from_attributes=True)
                await crud.sync.update(
                    uow.session, db_obj=sync, obj_in=sync_update, current_user=user, uow=uow
                )
            connection = schemas.Connection.model_validate(connection, from_attributes=True)
            await uow.commit()
            return connection

    async def get_connection_credentials(
        self, db: AsyncSession, connection_id: UUID, user: schemas.User
    ) -> Dict[str, Any]:
        """Get decrypted credentials for a connection.

        Args:
            db: The database session
            connection_id: The ID of the connection
            user: The current user

        Returns:
            The decrypted credentials

        Raises:
            NotFoundException: If the connection or credential is not found
        """
        connection = await crud.connection.get(db, id=connection_id, current_user=user)
        if not connection:
            raise NotFoundException("Connection not found")

        if not connection.integration_credential_id:
            raise NotFoundException("Connection has no integration credential")

        integration_credential = await crud.integration_credential.get(
            db, id=connection.integration_credential_id, current_user=user
        )

        if not integration_credential:
            raise NotFoundException("Integration credential not found")

        return credentials.decrypt(integration_credential.encrypted_credentials)

    # Private helper methods

    # async def _get_integration_by_type(
    #     self, db: AsyncSession, integration_type: IntegrationType, short_name: str
    # ) -> Union[schemas.Source, schemas.Destination, schemas.EmbeddingModel, None]:
    #     """Get integration based on its type.

    #     Args:
    #         db: The database session
    #         integration_type: The type of integration
    #         short_name: The short name of the integration

    #     Returns:
    #         The integration or None if not found
    #     """
    #     if integration_type == IntegrationType.SOURCE:
    #         return await crud.source.get_by_short_name(db, short_name)
    #     elif integration_type == IntegrationType.DESTINATION:
    #         return await crud.destination.get_by_short_name(db, short_name)
    #     elif integration_type == IntegrationType.EMBEDDING_MODEL:
    #         return await crud.embedding_model.get_by_short_name(db, short_name)
    #     return None

    # async def _create_connection_without_credential(
    #     self,
    #     uow: UnitOfWork,
    #     integration_type: IntegrationType,
    #     short_name: str,
    #     name: Optional[str],
    #     integration_name: str,
    #     user: schemas.User,
    # ) -> schemas.Connection:
    #     """Create a connection that doesn't require credentials.

    #     Args:
    #         uow: The unit of work
    #         integration_type: The type of integration
    #         short_name: The short name of the integration
    #         name: The name of the connection
    #         integration_name: The name of the integration
    #         user: The current user

    #     Returns:
    #         The created connection
    #     """
    #     connection_data = {
    #         "name": name if name else f"Connection to {integration_name}",
    #         "integration_type": integration_type,
    #         "status": ConnectionStatus.ACTIVE,
    #         "integration_credential_id": None,
    #         "short_name": short_name,
    #     }

    #     connection_in = ConnectionCreate(**connection_data)
    #     return await crud.connection.create(
    #         uow.session, obj_in=connection_in, current_user=user, uow=uow
    #     )

    async def _create_connection_with_credential(
        self,
        uow: UnitOfWork,
        integration_type: IntegrationType,
        short_name: str,
        name: Optional[str],
        integration_name: str,
        auth_type: AuthType,
        encrypted_credentials: str,
        auth_config_class: Optional[str],
        user: schemas.User,
    ) -> schemas.Connection:
        """Create a connection with credentials.

        Args:
            uow: The unit of work
            integration_type: The type of integration
            short_name: The short name of the integration
            name: The name of the connection
            integration_name: The name of the integration
            auth_type: The authentication type
            encrypted_credentials: The encrypted credentials
            auth_config_class: The auth config class name
            user: The current user

        Returns:
            The created connection
        """
        # Create integration credential
        integration_cred_in = schemas.IntegrationCredentialCreateEncrypted(
            name=f"{integration_name} - {user.email}",
            description=f"Credentials for {integration_name} - {user.email}",
            integration_short_name=short_name,
            integration_type=integration_type,
            auth_type=auth_type,
            encrypted_credentials=encrypted_credentials,
            auth_config_class=auth_config_class,
        )

        integration_cred = await crud.integration_credential.create(
            uow.session, obj_in=integration_cred_in, current_user=user, uow=uow
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
        return await crud.connection.create(
            uow.session, obj_in=connection_in, current_user=user, uow=uow
        )

    # async def _create_oauth2_connection(
    #     self,
    #     db: AsyncSession,
    #     source: schemas.Source,
    #     settings: Any,
    #     oauth2_response: OAuth2TokenResponse,
    #     user: schemas.User,
    #     connection_name: Optional[str] = None,
    #     auth_fields: Optional[dict] = None,
    # ) -> schemas.Connection:
    #     """Create a connection with OAuth2 credentials.

    #     Args:
    #         db: The database session
    #         source: The source
    #         settings: The OAuth2 settings
    #         oauth2_response: The OAuth2 token response
    #         user: The current user
    #         connection_name: Optional custom name for the connection
    #         auth_fields: Optional additional authentication fields for the connection

    #     Returns:
    #         The created connection
    #     """
    #     # Get the credentials to store
    #     credentials_data = oauth2_response.model_dump()

    #     # Store config fields in credentials if provided
    #     if auth_fields:
    #         for key, value in auth_fields.items():
    #             if key not in credentials_data:
    #                 credentials_data[key] = value

    #     encrypted_creds = credentials.encrypt(credentials_data)

    #     async with UnitOfWork(db) as uow:
    #         integration_cred_in = schemas.IntegrationCredentialCreateEncrypted(
    #             name=f"{source.name} OAuth2 - {user.email}",
    #             description=f"OAuth2 credentials for {source.name} - {user.email}",
    #             integration_short_name=source.short_name,
    #             integration_type=IntegrationType.SOURCE,
    #             auth_type=source.auth_type,
    #             encrypted_credentials=encrypted_creds,
    #         )

    #         integration_cred = await crud.integration_credential.create(
    #             uow.session, obj_in=integration_cred_in, current_user=user, uow=uow
    #         )
    #         await uow.session.flush()

    #         # Create connection with credentials
    #         connection_data = {
    #             "name": connection_name if connection_name else f"Connection to {source.name}",
    #             "integration_type": IntegrationType.SOURCE,
    #             "status": ConnectionStatus.ACTIVE,
    #             "integration_credential_id": integration_cred.id,
    #             "short_name": source.short_name,
    #         }

    #         connection_in = ConnectionCreate(**connection_data)
    #         connection = await crud.connection.create(
    #             uow.session, obj_in=connection_in, current_user=user, uow=uow
    #         )

    #         await uow.commit()
    #         await uow.session.refresh(connection)
    #         return connection

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

    def _supports_oauth2(self, auth_type: AuthType) -> bool:
        """Check if the auth type supports OAuth2."""
        return auth_type in (
            AuthType.oauth2,
            AuthType.oauth2_with_refresh,
            AuthType.oauth2_with_refresh_rotating,
        )

    async def create_integration_credential(
        self,
        db: AsyncSession,
        integration_type: IntegrationType,
        short_name: str,
        credential_in: schemas.IntegrationCredentialRawCreate,
        user: schemas.User,
    ) -> schemas.IntegrationCredentialInDB:
        """Create an integration credential with validation.

        Args:
            db: The database session
            integration_type: Type of integration
            short_name: Short name of the integration
            credential_in: The credential data with auth fields
            user: The current user

        Returns:
            The created integration credential with ID

        Raises:
            HTTPException: If validation fails or integration not found
        """
        # Get the integration based on type
        integration = None
        auth_type = None
        auth_config_class = None

        if integration_type == IntegrationType.SOURCE:
            integration = await crud.source.get_by_short_name(db, short_name=short_name)
            if integration:
                auth_type = integration.auth_type
                auth_config_class = integration.auth_config_class
        elif integration_type == IntegrationType.DESTINATION:
            integration = await crud.destination.get_by_short_name(db, short_name=short_name)
            if integration:
                auth_type = integration.auth_type
                auth_config_class = integration.auth_config_class
        elif integration_type == IntegrationType.EMBEDDING_MODEL:
            integration = await crud.embedding_model.get_by_short_name(db, short_name=short_name)
            if integration:
                auth_type = integration.auth_type
                auth_config_class = integration.auth_config_class

        if not integration:
            raise HTTPException(
                status_code=404, detail=f"Integration not found: {integration_type} {short_name}"
            )

        # Check if auth config class is defined
        BASE_ERROR_MESSAGE = (
            f"See https://docs.airweave.ai/docs/connectors/{short_name}#authentication "
            f"for more information."
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

        # Create the integration credential
        return await self._create_credential_in_db(
            db,
            credential_in,
            integration,
            integration_type,
            short_name,
            auth_type,
            encrypted_credentials,
            auth_config_class,
            user,
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
        auth_type,
        encrypted_credentials,
        auth_config_class,
        user,
    ):
        """Create the integration credential in the database."""
        async with UnitOfWork(db) as uow:
            integration_cred_in = schemas.IntegrationCredentialCreateEncrypted(
                name=credential_in.name,
                description=credential_in.description
                or f"Credentials for {integration.name} - {user.email}",
                integration_short_name=short_name,
                integration_type=integration_type,
                auth_type=auth_type,
                encrypted_credentials=encrypted_credentials,
                auth_config_class=auth_config_class,
            )

            integration_credential = await crud.integration_credential.create(
                uow.session, obj_in=integration_cred_in, current_user=user, uow=uow
            )

            await uow.commit()
            await uow.session.refresh(integration_credential)

            # Get the schema model from the database object and return
            return schemas.IntegrationCredentialInDB.model_validate(
                integration_credential, from_attributes=True
            )


connection_service = ConnectionService()
