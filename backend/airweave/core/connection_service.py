"""Service layer for managing connections to external services."""

from typing import Any, Dict, Optional, Union
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
from airweave.platform.auth.schemas import AuthType, OAuth2TokenResponse
from airweave.platform.auth.services import oauth2_service
from airweave.platform.auth.settings import integration_settings
from airweave.platform.locator import resource_locator
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

    async def connect_with_config(
        self,
        db: AsyncSession,
        integration_type: IntegrationType,
        short_name: str,
        name: Optional[str],
        config_fields: Dict[str, Any],
        user: schemas.User,
    ) -> schemas.Connection:
        """Connect to a service using configuration fields.

        Args:
            db: The database session
            integration_type: The type of integration
            short_name: The short name of the integration
            name: The name of the connection
            config_fields: The configuration fields
            user: The current user

        Returns:
            The created connection

        Raises:
            HTTPException: If the integration is not found or doesn't support config fields
        """
        async with UnitOfWork(db) as uow:
            integration = await self._get_integration_by_type(
                uow.session, integration_type, short_name
            )

            if not integration:
                raise HTTPException(
                    status_code=400,
                    detail=f"{integration_type} with short_name '{short_name}' does not exist",
                )

            # For AuthType.none sources, we don't need integration credentials
            if integration.auth_type == AuthType.none or integration.auth_type is None:
                connection = await self._create_connection_without_credential(
                    uow=uow,
                    integration_type=integration_type,
                    short_name=short_name,
                    name=name,
                    integration_name=integration.name,
                    user=user,
                )
                await uow.commit()
                await uow.session.refresh(connection)
                return connection

            # For config_class auth type, validate config fields
            if (
                integration.auth_type == AuthType.config_class
                or integration.auth_type == AuthType.sigv4
            ):
                if not integration.auth_config_class:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Integration {integration.name} does not have an auth config class",
                    )
                # Create and validate auth config
                auth_config_class = resource_locator.get_auth_config(
                    integration.auth_config_class, integration.auth_type
                )
                auth_config = auth_config_class(**config_fields)
                encrypted_creds = credentials.encrypt(auth_config.model_dump())

                # Create the connection with credentials
                connection = await self._create_connection_with_credential(
                    uow=uow,
                    integration_type=integration_type,
                    short_name=short_name,
                    name=name,
                    integration_name=integration.name,
                    auth_type=integration.auth_type,
                    encrypted_credentials=encrypted_creds,
                    auth_config_class=integration.auth_config_class,
                    user=user,
                )
                await uow.commit()
                await uow.session.refresh(connection)
                return connection
            else:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Integration {integration.name} does not support config fields, "
                        "use the UI to connect"
                    ),
                )

    async def get_oauth2_auth_url(self, short_name: str) -> str:
        """Get the OAuth2 authorization URL for a source.

        Args:
            short_name: The short name of the source

        Returns:
            The OAuth2 authorization URL

        Raises:
            HTTPException: If the integration doesn't support OAuth2
        """
        settings = integration_settings.get_by_short_name(short_name)
        if not settings:
            raise HTTPException(status_code=404, detail="Integration not found")

        if short_name == "trello":
            return oauth2_service.generate_auth_url_for_trello()

        if not self._supports_oauth2(settings.auth_type):
            raise HTTPException(status_code=400, detail="Integration does not support OAuth2")

        return oauth2_service.generate_auth_url(settings)

    async def connect_with_oauth2_code(
        self, db: AsyncSession, short_name: str, code: str, user: schemas.User
    ) -> schemas.Connection:
        """Create a connection using an OAuth2 code.

        Args:
            db: The database session
            short_name: The short name of the integration
            code: The OAuth2 authorization code
            user: The current user

        Returns:
            The created connection

        Raises:
            HTTPException: If code exchange fails
        """
        try:
            # Exchange the authorization code for a token
            oauth2_response = await oauth2_service.exchange_autorization_code_for_token(
                short_name, code
            )

            # Get the source information
            source = await crud.source.get_by_short_name(db, short_name)
            if not source:
                raise HTTPException(status_code=404, detail="Source not found")

            # Get OAuth2 settings
            settings = integration_settings.get_by_short_name(short_name)
            if not settings:
                raise HTTPException(status_code=404, detail="Integration settings not found")

            return await self._create_oauth2_connection(
                db=db,
                source=source,
                settings=settings,
                oauth2_response=oauth2_response,
                user=user,
            )
        except Exception as e:
            connection_logger.error(f"Failed to exchange OAuth2 code: {e}")
            raise HTTPException(status_code=400, detail="Failed to exchange OAuth2 code") from e

    async def connect_with_white_label_oauth2_code(
        self, db: AsyncSession, white_label_id: UUID, code: str, user: schemas.User
    ) -> schemas.Connection:
        """Connect using an OAuth2 code from a white label.

        Args:
            db: The database session
            white_label_id: The ID of the white label
            code: The OAuth2 code
            user: The current user

        Returns:
            The created connection

        Raises:
            HTTPException: If white label is not found or code exchange fails
        """
        try:
            white_label = await crud.white_label.get(db, id=white_label_id, current_user=user)
            if not white_label:
                raise HTTPException(status_code=404, detail="White label integration not found")

            return await oauth2_service.create_oauth2_connection_for_whitelabel(
                db=db, white_label=white_label, code=code, user=user
            )
        except HTTPException as e:
            # Re-raise HTTPExceptions directly to preserve the status code
            connection_logger.error(f"Failed to exchange OAuth2 code for white label: {e}")
            raise
        except Exception as e:
            connection_logger.error(f"Failed to exchange OAuth2 code for white label: {e}")
            raise HTTPException(
                status_code=400, detail="Failed to exchange OAuth2 code for white label"
            ) from e

    async def get_white_label_oauth2_auth_url(
        self, db: AsyncSession, white_label_id: UUID, user: schemas.User
    ) -> str:
        """Get the OAuth2 authorization URL for a white label integration.

        Args:
            db: The database session
            white_label_id: The ID of the white label
            user: The current user

        Returns:
            The OAuth2 authorization URL

        Raises:
            HTTPException: If white label is not found
        """
        try:
            white_label = await crud.white_label.get(db, id=white_label_id, current_user=user)
            if not white_label:
                raise HTTPException(status_code=404, detail="White label integration not found")

            return await oauth2_service.generate_auth_url_for_whitelabel(db, white_label)
        except Exception as e:
            connection_logger.error(f"Failed to generate auth URL for white label: {e}")
            raise HTTPException(status_code=400, detail="Failed to generate auth URL") from e

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

    async def _get_integration_by_type(
        self, db: AsyncSession, integration_type: IntegrationType, short_name: str
    ) -> Union[schemas.Source, schemas.Destination, schemas.EmbeddingModel, None]:
        """Get integration based on its type.

        Args:
            db: The database session
            integration_type: The type of integration
            short_name: The short name of the integration

        Returns:
            The integration or None if not found
        """
        if integration_type == IntegrationType.SOURCE:
            return await crud.source.get_by_short_name(db, short_name)
        elif integration_type == IntegrationType.DESTINATION:
            return await crud.destination.get_by_short_name(db, short_name)
        elif integration_type == IntegrationType.EMBEDDING_MODEL:
            return await crud.embedding_model.get_by_short_name(db, short_name)
        return None

    async def _create_connection_without_credential(
        self,
        uow: UnitOfWork,
        integration_type: IntegrationType,
        short_name: str,
        name: Optional[str],
        integration_name: str,
        user: schemas.User,
    ) -> schemas.Connection:
        """Create a connection that doesn't require credentials.

        Args:
            uow: The unit of work
            integration_type: The type of integration
            short_name: The short name of the integration
            name: The name of the connection
            integration_name: The name of the integration
            user: The current user

        Returns:
            The created connection
        """
        connection_data = {
            "name": name if name else f"Connection to {integration_name}",
            "integration_type": integration_type,
            "status": ConnectionStatus.ACTIVE,
            "integration_credential_id": None,
            "short_name": short_name,
        }

        connection_in = ConnectionCreate(**connection_data)
        return await crud.connection.create(
            uow.session, obj_in=connection_in, current_user=user, uow=uow
        )

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

    async def _create_oauth2_connection(
        self,
        db: AsyncSession,
        source: schemas.Source,
        settings: Any,
        oauth2_response: OAuth2TokenResponse,
        user: schemas.User,
    ) -> schemas.Connection:
        """Create a connection with OAuth2 credentials.

        Args:
            db: The database session
            source: The source
            settings: The OAuth2 settings
            oauth2_response: The OAuth2 token response
            user: The current user

        Returns:
            The created connection
        """
        # Get the credentials to store
        credentials_data = oauth2_response.model_dump()
        encrypted_creds = credentials.encrypt(credentials_data)

        async with UnitOfWork(db) as uow:
            integration_cred_in = schemas.IntegrationCredentialCreateEncrypted(
                name=f"{source.name} OAuth2 - {user.email}",
                description=f"OAuth2 credentials for {source.name} - {user.email}",
                integration_short_name=source.short_name,
                integration_type=IntegrationType.SOURCE,
                auth_type=source.auth_type,
                encrypted_credentials=encrypted_creds,
            )

            integration_cred = await crud.integration_credential.create(
                uow.session, obj_in=integration_cred_in, current_user=user, uow=uow
            )
            await uow.session.flush()

            # Create connection with credentials
            connection_data = {
                "name": f"Connection to {source.name}",
                "integration_type": IntegrationType.SOURCE,
                "status": ConnectionStatus.ACTIVE,
                "integration_credential_id": integration_cred.id,
                "short_name": source.short_name,
            }

            connection_in = ConnectionCreate(**connection_data)
            connection = await crud.connection.create(
                uow.session, obj_in=connection_in, current_user=user, uow=uow
            )

            await uow.commit()
            await uow.session.refresh(connection)
            return connection

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


connection_service = ConnectionService()
