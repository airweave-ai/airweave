"""Service for managing source connections."""

from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core import credentials
from airweave.core.auth_provider_service import auth_provider_service
from airweave.core.collection_service import collection_service
from airweave.core.constants.native_connections import NATIVE_QDRANT_UUID, NATIVE_TEXT2VEC_UUID
from airweave.core.shared_models import ConnectionStatus, SourceConnectionStatus, SyncStatus
from airweave.core.sync_service import sync_service
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.integration_credential import IntegrationType
from airweave.platform.auth.schemas import AuthType, OAuth2TokenResponse
from airweave.platform.auth.services import oauth2_service
from airweave.platform.auth.settings import integration_settings
from airweave.platform.configs.auth import OAuth2AuthConfig, OAuth2BYOCAuthConfig
from airweave.platform.locator import resource_locator
from airweave.platform.temporal.schedule_service import temporal_schedule_service


class SourceConnectionService:
    """Service for managing source connections.

    This service encapsulates the complex transactions required for source connections,
    including:
    - Creating source connections with related objects (integration credential, sync, dag)
    - Updating source connections and keeping related objects in sync
    - Deleting source connections and all related objects
    - Running sync jobs for source connections
    """

    async def _is_non_byoc_oauth_source(self, db: AsyncSession, source_short_name: str) -> bool:
        """Check if a source uses OAuth authentication.

        Args:
            db: The database session
            source_short_name: The short name of the source

        Returns:
            True if the source uses any form of OAuth authentication
        """
        # Get the source info
        source = await crud.source.get_by_short_name(db, short_name=source_short_name)
        if not source or not source.auth_config_class:
            return False

        try:
            # Get the auth config class
            auth_config_class = resource_locator.get_auth_config(source.auth_config_class)

            # Check if it's OAuth-based by checking inheritance
            return issubclass(auth_config_class, OAuth2AuthConfig) and not issubclass(
                auth_config_class, OAuth2BYOCAuthConfig
            )
        except Exception:
            # If we can't load the class, assume it's not OAuth
            return False

    async def _validate_auth_fields(
        self,
        db: AsyncSession,
        source_short_name: str,
        auth_fields: Optional[Dict[str, Any]],
        ctx: ApiContext,
    ) -> dict:
        """Validate auth fields based on auth type.

        Only works for config_class auth type.

        Args:
            db: The database session
            source_short_name: The short name of the source
            auth_fields: The auth fields to validate
            ctx: The current authentication context

        Returns:
            The validated auth fields as a dict

        Raises:
            HTTPException: If auth fields are invalid or not supported
        """
        # Get the source info
        source = await crud.source.get_by_short_name(db, short_name=source_short_name)
        if not source:
            raise HTTPException(status_code=404, detail=f"Source '{source_short_name}' not found")

        BASE_ERROR_MESSAGE = (
            f"See https://docs.airweave.ai/{source.short_name}#authentication for more information."
        )

        # Check if auth_config_class is defined for the source
        if not source.auth_config_class:
            raise HTTPException(
                status_code=422,
                detail=f"Source {source.name} does not have an auth configuration defined. "
                + BASE_ERROR_MESSAGE,
            )

        if auth_fields is None:
            raise HTTPException(
                status_code=422,
                detail=f"Source {source.name} requires auth fields. " + BASE_ERROR_MESSAGE,
            )

        # Create and validate auth config
        try:
            auth_config_class = resource_locator.get_auth_config(source.auth_config_class)
            auth_config = auth_config_class(**auth_fields)
            return auth_config.model_dump()
        except Exception as e:
            ctx.logger.error(f"Failed to validate auth fields: {e}")

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
                    f"Invalid configuration for {source.auth_config_class}:\n"
                    + "\n".join(error_messages)
                )
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid auth fields: {error_detail}. " + BASE_ERROR_MESSAGE,
                ) from e
            else:
                # For other types of errors
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid auth fields: {str(e)}. " + BASE_ERROR_MESSAGE,
                ) from e

    async def _validate_config_fields(
        self,
        db: AsyncSession,
        source_short_name: str,
        config_fields: Optional[Dict[str, Any]],
        ctx: ApiContext,
    ) -> dict:
        """Validate config fields based on source config class.

        Args:
            db: The database session
            source_short_name: The short name of the source
            config_fields: The config fields to validate
            ctx: The current authentication context

        Returns:
            The validated config fields as a dict

        Raises:
            HTTPException: If config fields are invalid or required but not provided
        """
        # Get the source info
        source = await crud.source.get_by_short_name(db, short_name=source_short_name)
        if not source:
            raise HTTPException(status_code=404, detail=f"Source '{source_short_name}' not found")

        BASE_ERROR_MESSAGE = (
            f"See https://docs.airweave.ai/{source.short_name}#configuration for more information."
        )

        # Check if source has a config class defined - it MUST be defined
        if not hasattr(source, "config_class") or source.config_class is None:
            raise HTTPException(
                status_code=422,
                detail=f"Source {source.name} does not have a configuration class defined. "
                + BASE_ERROR_MESSAGE,
            )

        # Config class exists but no config fields provided - check if that's allowed
        if config_fields is None:
            try:
                # Get config class to check if it has required fields
                config_class = resource_locator.get_config(source.config_class)
                # Create an empty instance to see if it accepts no fields
                config = config_class()
                return config.model_dump()
            except Exception:
                # If it fails with no fields, config is required
                raise HTTPException(
                    status_code=422,
                    detail=f"Source {source.name} requires config fields but none were provided. "
                    + BASE_ERROR_MESSAGE,
                ) from None

        # Both config class and config fields exist, validate them
        try:
            config_class = resource_locator.get_config(source.config_class)
            config = config_class(**config_fields)
            return config.model_dump()
        except Exception as e:
            ctx.logger.error(f"Failed to validate config fields: {e}")

            # Check if it's a Pydantic validation error and format it nicely
            from pydantic import ValidationError

            if isinstance(e, ValidationError):
                # Extract the field names and error messages
                error_messages = []
                for error in e.errors():
                    field = ".".join(str(loc) for loc in error.get("loc", []))
                    msg = error.get("msg", "")
                    error_messages.append(f"Field '{field}': {msg}")

                error_detail = f"Invalid configuration for {source.config_class}:\n" + "\n".join(
                    error_messages
                )
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid config fields: {error_detail}. " + BASE_ERROR_MESSAGE,
                ) from e
            else:
                # For other types of errors
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid config fields: {str(e)}. " + BASE_ERROR_MESSAGE,
                ) from e

    async def _handle_oauth_validation(
        self, db: AsyncSession, source: Any, source_connection_in: Any, aux_attrs: Dict[str, Any]
    ) -> None:
        """Validate OAuth sources cannot be created with auth_fields through API."""
        if aux_attrs.get("auth_fields") and await self._is_non_byoc_oauth_source(
            db, source_connection_in.short_name
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Source '{source.name}' requires OAuth authentication and cannot be "
                    f"created through the API. Please use the UI to authenticate through "
                    f"the OAuth consent screen. Visit https://app.airweave.ai "
                    f"to connect this source."
                ),
            )

    async def _validate_auth_provider_and_config(
        self,
        db: AsyncSession,
        auth_provider_readable_id: str,
        auth_provider_config: Optional[Dict[str, Any]],
        ctx: ApiContext,
    ) -> Dict[str, Any]:
        """Validate auth provider exists and config fields are valid.

        Args:
            db: The database session
            auth_provider_readable_id: The readable ID of the auth provider
            auth_provider_config: The auth provider config to validate (can be ConfigValues or dict)
            ctx: The current authentication context

        Returns:
            The validated auth provider config

        Raises:
            HTTPException: If auth provider doesn't exist or config is invalid
        """
        # Convert ConfigValues to dict if needed
        auth_provider_config_dict = None
        if auth_provider_config is not None:
            if hasattr(auth_provider_config, "model_dump"):
                auth_provider_config_dict = auth_provider_config.model_dump()
            else:
                auth_provider_config_dict = auth_provider_config

        # 1. Check if auth provider connection exists by readable_id
        auth_provider_connection = await crud.connection.get_by_readable_id(
            db, readable_id=auth_provider_readable_id, ctx=ctx
        )
        if not auth_provider_connection:
            raise HTTPException(
                status_code=404,
                detail=f"Auth provider connection with readable_id '{auth_provider_readable_id}' "
                "not found. To see which auth providers are supported and learn more about how to "
                "use them, check [this page](https://docs.airweave.ai/docs/auth-providers).",
            )

        # 2. Validate the auth provider config using the auth provider service method
        validated_config = await auth_provider_service.validate_auth_provider_config(
            db, auth_provider_connection.short_name, auth_provider_config_dict
        )

        return validated_config

    async def _get_or_create_collection(
        self,
        uow: Any,
        core_attrs: Dict[str, Any],
        source_connection_in: Any,
        ctx: ApiContext,
    ) -> Any:
        """Get existing collection or create new one."""
        if "collection" not in core_attrs:
            collection_create = schemas.CollectionCreate(
                name=f"Collection for {source_connection_in.name}",
                description=f"Auto-generated collection for {source_connection_in.name}",
            )
            return await collection_service.create(
                db=uow.session,
                collection_in=collection_create,
                ctx=ctx,
                uow=uow,
            )
        else:
            readable_collection_id = core_attrs["collection"]
            if "collection" in core_attrs:
                del core_attrs["collection"]
            collection = await crud.collection.get_by_readable_id(
                db=uow.session, readable_id=readable_collection_id, ctx=ctx
            )
            if not collection:
                raise HTTPException(
                    status_code=404, detail=f"Collection '{readable_collection_id}' not found"
                )
            return collection

    async def create_source_connection(
        self,
        db: AsyncSession,
        source_connection_in: Union[
            schemas.SourceConnectionCreate,
            schemas.SourceConnectionCreateWithWhiteLabel,
            schemas.SourceConnectionCreateWithCredential,
        ],
        ctx: ApiContext,
    ) -> Tuple[schemas.SourceConnection, Optional[schemas.SyncJob]]:
        """Create a new source connection with all related objects.

        This method:
        1. Creates a credential with auth fields if provided, or uses existing credential
        2. Creates the connection to the source (schemas.Connection)
        3. Creates a collection if not provided
        4. Creates a sync configuration and DAG
        5. Creates a sync job if immediate execution is requested
        6. Creates the source connection (schemas.SourceConnection)

        Args:
            db: The database session
            source_connection_in: The source connection to create. Can be one of:
                - SourceConnectionCreate: For public API (auth_fields only)
                - SourceConnectionCreateWithWhiteLabel: For white label source connections
                - SourceConnectionCreateWithCredential: For internal use with existing credentials
            ctx: The API context

        Returns:
            A tuple of (source_connection, sync_job)

        Raises:
            HTTPException: If the source is not found
        """
        # Separate core and auxiliary attributes
        core_attrs, aux_attrs = source_connection_in.map_to_core_and_auxiliary_attributes()

        async with UnitOfWork(db) as uow:
            # Get the source information
            source = await crud.source.get_by_short_name(
                db, short_name=source_connection_in.short_name
            )
            if not source:
                raise HTTPException(
                    status_code=404, detail=f"Source not found: {source_connection_in.short_name}"
                )

            integration_credential_id = None

            if core_attrs.get("auth_provider"):
                # Validate auth provider and get validated config
                validated_auth_provider_config = await self._validate_auth_provider_and_config(
                    db=uow.session,
                    auth_provider_readable_id=core_attrs.get("auth_provider"),
                    auth_provider_config=core_attrs.get("auth_provider_config"),
                    ctx=ctx,
                )

                # Update the core_attrs with validated config
                core_attrs["auth_provider_config"] = validated_auth_provider_config

                # For auth provider connections, we don't create integration credentials
                # but we will create a connection without credentials
            elif aux_attrs.get("credential_id"):
                integration_credential = await crud.integration_credential.get(
                    uow.session, id=aux_attrs["credential_id"], ctx=ctx
                )
                if not integration_credential:
                    raise HTTPException(status_code=404, detail="Integration credential not found")

                if (
                    integration_credential.integration_short_name != source_connection_in.short_name
                    or integration_credential.integration_type != IntegrationType.SOURCE
                ):
                    raise HTTPException(
                        status_code=400, detail="Credential doesn't match the source type"
                    )
                integration_credential_id = integration_credential.id
            elif aux_attrs.get("auth_fields"):
                # If auth fields are given, the source cannot be OAuth
                await self._handle_oauth_validation(db, source, source_connection_in, aux_attrs)

                auth_fields = await self._validate_auth_fields(
                    uow.session, source_connection_in.short_name, aux_attrs["auth_fields"], ctx
                )

                integration_cred_in = schemas.IntegrationCredentialCreateEncrypted(
                    name=f"{source.name} - {ctx.organization.id}",
                    description=f"Credentials for {source.name} - {ctx.organization.id}",
                    integration_short_name=source_connection_in.short_name,
                    integration_type=IntegrationType.SOURCE,
                    auth_type=source.auth_type,
                    encrypted_credentials=credentials.encrypt(auth_fields),
                    auth_config_class=source.auth_config_class,
                )

                integration_credential = await crud.integration_credential.create(
                    uow.session, obj_in=integration_cred_in, ctx=ctx, uow=uow
                )
                await uow.session.flush()
                integration_credential_id = integration_credential.id
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Either auth_provider, auth_fields or credential_id must be "
                    "provided to create a source connection",
                )

            # Validate config fields
            config_fields = await self._validate_config_fields(
                db, source_connection_in.short_name, core_attrs.get("config_fields"), ctx
            )
            core_attrs["config_fields"] = config_fields

            # Create the connection object for source (system table)
            # For auth_provider connections, integration_credential_id will be None
            connection_create = schemas.ConnectionCreate(
                name=source_connection_in.name,
                integration_type=IntegrationType.SOURCE,
                integration_credential_id=integration_credential_id,  # None for auth_provider
                status=ConnectionStatus.ACTIVE,
                short_name=source_connection_in.short_name,
            )

            connection = await crud.connection.create(
                db=uow.session, obj_in=connection_create, ctx=ctx, uow=uow
            )
            await uow.session.flush()
            connection_id = connection.id

            # Get or create collection
            collection = await self._get_or_create_collection(
                uow, core_attrs, source_connection_in, ctx
            )

            # Create the sync
            sync_in = schemas.SyncCreate(
                name=f"Sync for {source_connection_in.name}",
                description=f"Auto-generated sync for {source_connection_in.name}",
                source_connection_id=connection_id,  # ID of connection system table
                embedding_model_connection_id=NATIVE_TEXT2VEC_UUID,
                destination_connection_ids=[NATIVE_QDRANT_UUID],
                cron_schedule=aux_attrs["cron_schedule"],
                status=SyncStatus.ACTIVE,
                run_immediately=aux_attrs["sync_immediately"],
            )

            # Use the sync service to create the sync and automatically the DAG
            sync, sync_job = await sync_service.create_and_run_sync(
                db=uow.session, sync_in=sync_in, ctx=ctx, uow=uow
            )

            # Create the source connection from core attributes
            # IMPORTANT: We explicitly include auth_provider and auth_provider_config
            # so that future token refreshes can use the same auth provider instead of
            # attempting direct OAuth refresh (which would fail with wrong client_id/secret)

            # Remove auth_provider from core_attrs since we need to map it to readable_id
            core_attrs_for_db = {k: v for k, v in core_attrs.items() if k != "auth_provider"}

            source_connection_create = {
                **core_attrs_for_db,
                "connection_id": connection_id,
                "readable_collection_id": collection.readable_id,
                "sync_id": sync.id,
                "white_label_id": core_attrs.get(
                    "white_label_id"
                ),  # Include white_label_id if provided
                "readable_auth_provider_id": core_attrs.get(
                    "auth_provider"
                ),  # Map auth_provider to database column name
                "auth_provider_config": core_attrs.get(
                    "auth_provider_config"
                ),  # Store auth provider config for future use
            }

            source_connection = await crud.source_connection.create(
                db=uow.session, obj_in=source_connection_create, ctx=ctx, uow=uow
            )
            await uow.session.flush()

            # map to schemas and return
            source_connection = schemas.SourceConnection.from_orm_with_collection_mapping(
                source_connection
            )

            # Only validate sync_job if it exists (when sync_immediately=True)
            if sync_job is not None:
                sync_job = schemas.SyncJob.model_validate(sync_job, from_attributes=True)

                # Update the source connection status with sync job info
                source_connection.status = SourceConnectionStatus.IN_PROGRESS
                source_connection.latest_sync_job_status = sync_job.status
                source_connection.latest_sync_job_id = sync_job.id
                source_connection.latest_sync_job_started_at = sync_job.started_at
                source_connection.latest_sync_job_completed_at = sync_job.completed_at
                source_connection.latest_sync_job_error = sync_job.error if sync_job.error else None
            else:
                # No sync job created (sync_immediately=False)
                source_connection.status = SourceConnectionStatus.ACTIVE
                source_connection.latest_sync_job_status = None
                source_connection.latest_sync_job_id = None
                source_connection.latest_sync_job_started_at = None
                source_connection.latest_sync_job_completed_at = None

            # Hide auth fields by default
            source_connection.auth_fields = "********"

        return source_connection, sync_job

    async def get_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
        show_auth_fields: bool = False,
    ) -> schemas.SourceConnection:
        """Get a source connection with all related data.

        This method enriches the source connection with data from related objects:
        1. Connection information
        2. Integration credential and decrypted auth fields (if exists)
        3. Sync information and latest sync job status (if exists)
        4. Collection information (if exists)

        Args:
            db: The database session
            source_connection_id: The ID of the source connection
            ctx: The current authentication context
            show_auth_fields: Whether to show the auth fields

        Returns:
            The enriched source connection

        Raises:
            HTTPException: If the source connection is not found
        """
        # Get the source connection from database
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, ctx=ctx
        )

        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        # Convert to schema model to start building the response
        source_connection_schema = schemas.SourceConnection.from_orm_with_collection_mapping(
            source_connection
        )

        # 1. Get the connection and its credentials if they exist
        if source_connection.connection_id:
            connection = await crud.connection.get(
                db=db, id=source_connection.connection_id, ctx=ctx
            )

            if connection and connection.integration_credential_id:
                # Get and decrypt the integration credential
                integration_credential = await crud.integration_credential.get(
                    db=db, id=connection.integration_credential_id, ctx=ctx
                )

                if integration_credential and integration_credential.encrypted_credentials:
                    if show_auth_fields:
                        # Decrypt credentials and attach to source connection
                        decrypted_auth_fields = credentials.decrypt(
                            integration_credential.encrypted_credentials
                        )
                        source_connection_schema.auth_fields = decrypted_auth_fields
                    else:
                        source_connection_schema.auth_fields = "********"

        # 2. Get the sync schedule information if sync_id exists
        if source_connection.sync_id:
            sync = await crud.sync.get(db=db, id=source_connection.sync_id, ctx=ctx)
            if sync:
                # Add cron_schedule and next_scheduled_run to the response
                source_connection_schema.cron_schedule = sync.cron_schedule
                source_connection_schema.next_scheduled_run = sync.next_scheduled_run

                # Log the sync schedule information for debugging
                ctx.logger.info(
                    f"Adding sync schedule to source connection: "
                    f"cron_schedule={sync.cron_schedule}, "
                    f"next_scheduled_run={sync.next_scheduled_run}"
                )

        # Before returning, add a log to see what's actually being sent
        ctx.logger.info(
            "\nRETURNING SOURCE CONNECTION: "
            f"latest_sync_job_id={source_connection_schema.latest_sync_job_id},\n"
            f"cron_schedule={source_connection_schema.cron_schedule},\n"
            f"next_scheduled_run={source_connection_schema.next_scheduled_run},\n"
            "all job info="
            f"{source_connection_schema if 'source_connection_schema' in locals() else 'None'}\n"
        )

        return source_connection_schema

    async def get_all_source_connections(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        skip: int = 0,
        limit: int = 100,
    ) -> List[schemas.SourceConnectionListItem]:
        """Get all source connections for a user with minimal core attributes.

        This version uses a simplified schema (SourceConnectionListItem) that includes
        only the core attributes directly from the source connection model.

        Args:
            db: The database session
            ctx: The current authentication context
            skip: The number of source connections to skip
            limit: The maximum number of source connections to return

        Returns:
            A list of simplified source connection list items
        """
        # Get all source connections for the user
        source_connections = await crud.source_connection.get_multi(
            db=db, ctx=ctx, skip=skip, limit=limit
        )

        if not source_connections:
            return []

        # Create list items directly from source connections
        list_items = [
            schemas.SourceConnectionListItem(
                id=sc.id,
                name=sc.name,
                description=sc.description,
                short_name=sc.short_name,
                status=sc.status,
                created_at=sc.created_at,
                modified_at=sc.modified_at,
                sync_id=sc.sync_id,
                collection=sc.readable_collection_id,  # map to collection
                white_label_id=sc.white_label_id,  # Include white_label_id
            )
            for sc in source_connections
        ]

        return list_items

    async def get_source_connections_by_collection(
        self,
        db: AsyncSession,
        collection: str,
        ctx: ApiContext,
        skip: int = 0,
        limit: int = 100,
    ) -> List[schemas.SourceConnectionListItem]:
        """Get all source connections for a user by collection.

        Args:
            db: The database session
            collection: The collection to filter by
            ctx: The current authentication context
            skip: The number of source connections to skip
            limit: The maximum number of source connections to return

        Returns:
            A list of source connections
        """
        source_connections = await crud.source_connection.get_for_collection(
            db=db,
            readable_collection_id=collection,
            ctx=ctx,
            skip=skip,
            limit=limit,
        )

        if not source_connections:
            return []

        # Create list items directly from source connections
        list_items = [
            schemas.SourceConnectionListItem(
                id=sc.id,
                name=sc.name,
                description=sc.description,
                short_name=sc.short_name,
                status=sc.status,
                created_at=sc.created_at,
                modified_at=sc.modified_at,
                sync_id=sc.sync_id,
                collection=sc.readable_collection_id,  # map to collection
                white_label_id=sc.white_label_id,  # Include white_label_id
            )
            for sc in source_connections
        ]

        return list_items

    async def update_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        source_connection_in: schemas.SourceConnectionUpdate,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Update a source connection and related objects.

        This method:
        1. Updates the source connection
        2. Updates the sync cron schedule if changed
        3. Updates the auth fields in the integration credential if provided

        Args:
            db: The database session
            source_connection_id: The ID of the source connection to update
            source_connection_in: The updated source connection data
            ctx: The current authentication context

        Returns:
            The updated source connection

        Raises:
            HTTPException: If the source connection is not found
        """
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, ctx=ctx
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        async with UnitOfWork(db) as uow:
            # Validate config fields if they're being updated
            if source_connection_in.config_fields is not None:
                validated_config_fields = await self._validate_config_fields(
                    uow.session,
                    source_connection.short_name,
                    (
                        source_connection_in.config_fields.model_dump()
                        if hasattr(source_connection_in.config_fields, "model_dump")
                        else source_connection_in.config_fields
                    ),
                    ctx,
                )
                source_connection_in.config_fields = validated_config_fields

            # 1. Update source connection
            source_connection = await crud.source_connection.update(
                db=uow.session,
                db_obj=source_connection,
                obj_in=source_connection_in,
                ctx=ctx,
                uow=uow,
            )

            # 2. If cron_schedule was updated, also update the related sync
            if source_connection_in.cron_schedule is not None and source_connection.sync_id:
                sync = await crud.sync.get(
                    uow.session,
                    id=source_connection.sync_id,
                    ctx=ctx,
                    with_connections=False,
                )
                if sync:
                    sync_update = schemas.SyncUpdate(
                        cron_schedule=source_connection_in.cron_schedule
                    )
                    await crud.sync.update(
                        uow.session,
                        db_obj=sync,
                        obj_in=sync_update,
                        ctx=ctx,
                        uow=uow,
                    )

            # 3. If auth_fields are provided, update the integration credential
            if source_connection_in.auth_fields and source_connection.connection_id:
                # First get the connection to get the credential ID
                connection = await crud.connection.get(
                    uow.session, id=source_connection.connection_id, ctx=ctx
                )

                if connection and connection.integration_credential_id:
                    # Get the credential and update it
                    integration_credential = await crud.integration_credential.get(
                        uow.session,
                        id=connection.integration_credential_id,
                        ctx=ctx,
                    )

                    if integration_credential:
                        auth_fields_dict = source_connection_in.auth_fields.model_dump()
                        validated_auth_fields = await self._validate_auth_fields(
                            uow.session,
                            source_connection.short_name,
                            auth_fields_dict,
                            ctx,
                        )
                        credential_update = schemas.IntegrationCredentialUpdate(
                            encrypted_credentials=credentials.encrypt(validated_auth_fields)
                        )
                        await crud.integration_credential.update(
                            uow.session,
                            db_obj=integration_credential,
                            obj_in=credential_update,
                            ctx=ctx,
                            uow=uow,
                        )

            await uow.commit()

            # Get the updated source connection with related data
            return await self.get_source_connection(
                db=uow.session,
                source_connection_id=source_connection_id,
                ctx=ctx,
            )

    async def delete_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Delete a source connection and all related components.

        This method:
        1. Deletes all synced data from destination
        2. Deletes the sync if it exists
        3. Deletes the integration credential if it exists
        4. Deletes the source connection

        Args:
            db: The database session
            source_connection_id: The ID of the source connection to delete
            ctx: The current authentication context

        Returns:
            The deleted source connection

        Raises:
            HTTPException: If the source connection is not found
        """
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, ctx=ctx
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        # Save a copy of the source_connection for returning
        source_connection_schema = schemas.SourceConnection.from_orm_with_collection_mapping(
            source_connection
        )

        # Always delete data from Qdrant when deleting a source connection
        if source_connection.sync_id and source_connection.readable_collection_id:
            try:
                ctx.logger.info(
                    f"Deleting data for source connection {source_connection_id} "
                    f"(sync_id: {source_connection.sync_id}) from destinations"
                )

                # Get the collection
                collection = await crud.collection.get_by_readable_id(
                    db=db,
                    readable_id=source_connection.readable_collection_id,
                    ctx=ctx,
                )

                if collection:
                    # Import here to avoid circular dependency
                    from airweave.platform.destinations.qdrant import QdrantDestination

                    # Create Qdrant destination and delete by sync_id
                    destination = await QdrantDestination.create(collection_id=collection.id)
                    await destination.delete_by_sync_id(source_connection.sync_id)

                    ctx.logger.info(
                        f"Successfully deleted data for sync_id {source_connection.sync_id} "
                        f"from Qdrant collection {collection.id}"
                    )
                else:
                    ctx.logger.warning(
                        f"Collection {source_connection.readable_collection_id} not found, "
                        f"skipping data deletion"
                    )
            except Exception as e:
                ctx.logger.error(
                    f"Error deleting data from destinations: {str(e)}. "
                    f"Continuing with source connection deletion."
                )
                # We don't raise here - we still want to delete the source connection
                # even if data deletion fails

        # Cleanup Temporal schedules first (if any)
        if source_connection.sync_id:
            try:
                await temporal_schedule_service.delete_all_schedules_for_sync(
                    sync_id=source_connection.sync_id, db=db, ctx=ctx
                )
            except Exception as e:
                ctx.logger.error(
                    f"Failed to delete schedules for sync {source_connection.sync_id}: {e}"
                )

        await crud.source_connection.remove(db=db, id=source_connection_id, ctx=ctx)

        return source_connection_schema

    async def run_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
        access_token: Optional[str] = None,
    ) -> schemas.SyncJob:
        """Trigger a sync run for a source connection.

        Args:
            db: The database session
            source_connection_id: The ID of the source connection to run
            ctx: The current authentication context
            access_token: Optional access token to use instead of stored credentials

        Returns:
            The created sync job

        Raises:
            HTTPException: If the source connection is not found or has no associated sync
        """
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, ctx=ctx
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        if not source_connection.sync_id:
            raise HTTPException(status_code=400, detail="Source connection has no associated sync")

        # Trigger the sync run using the sync service
        sync, sync_job, sync_dag = await sync_service.trigger_sync_run(
            db=db, sync_id=source_connection.sync_id, ctx=ctx
        )

        # Store access token directly without validation if provided
        if access_token:
            sync_job.access_token = access_token

        return sync_job

    async def get_source_connection_jobs(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
    ) -> list[schemas.SourceConnectionJob]:
        """Get all sync jobs for a source connection.

        Args:
            db: The database session
            source_connection_id: The ID of the source connection
            ctx: The current authentication context

        Returns:
            A list of sync jobs

        Raises:
            HTTPException: If the source connection is not found
        """
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, ctx=ctx
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        if not source_connection.sync_id:
            return []

        # Get all jobs for the sync
        sync_jobs = await sync_service.list_sync_jobs(
            db=db, ctx=ctx, sync_id=source_connection.sync_id
        )

        # Map SyncJob objects to SourceConnectionJob objects
        source_connection_jobs = []
        for job in sync_jobs:
            # Create a new SourceConnectionJob with data from SyncJob
            sync_job_schema = schemas.SyncJob.model_validate(job, from_attributes=True)
            source_connection_job = sync_job_schema.to_source_connection_job(source_connection_id)
            source_connection_jobs.append(source_connection_job)

        return source_connection_jobs

    async def get_source_connection_job(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        job_id: UUID,
        ctx: ApiContext,
    ) -> schemas.SourceConnectionJob:
        """Get a specific sync job for a source connection.

        Args:
            db: The database session
            source_connection_id: The ID of the source connection
            job_id: The ID of the sync job
            ctx: The current authentication context

        Returns:
            The sync job

        Raises:
            HTTPException: If the source connection or job is not found
        """
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, ctx=ctx
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        if not source_connection.sync_id:
            raise HTTPException(status_code=404, detail="Source connection has no associated sync")

        # Get the specific job for the sync
        sync_job = await sync_service.get_sync_job(
            db=db, job_id=job_id, ctx=ctx, sync_id=source_connection.sync_id
        )

        sync_job_schema = schemas.SyncJob.model_validate(sync_job, from_attributes=True)

        # Convert to SourceConnectionJob format
        source_connection_job = sync_job_schema.to_source_connection_job(source_connection_id)

        return source_connection_job

    async def update_source_connection_status(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        status: SourceConnectionStatus,
        ctx: ApiContext,
    ) -> schemas.SourceConnection:
        """Update the status of a source connection.

        This also updates the related sync status to match.

        Args:
            db: The database session
            source_connection_id: The ID of the source connection
            status: The new status
            ctx: The current authentication context

        Returns:
            The updated source connection

        Raises:
            HTTPException: If the source connection is not found
        """
        source_connection = await crud.source_connection.get(
            db=db, id=source_connection_id, ctx=ctx
        )
        if not source_connection:
            raise HTTPException(status_code=404, detail="Source connection not found")

        async with UnitOfWork(db) as uow:
            # Update source connection status
            source_connection = await crud.source_connection.update_status(
                db=uow.session,
                id=source_connection_id,
                status=status,
                ctx=ctx,
            )

            # Update connection status if it exists
            if hasattr(source_connection, "connection_id") and source_connection.connection_id:
                connection = await crud.connection.get(
                    uow.session, id=source_connection.connection_id, ctx=ctx
                )
                if connection:
                    connection_status = (
                        ConnectionStatus.ACTIVE
                        if status == SourceConnectionStatus.ACTIVE
                        else ConnectionStatus.INACTIVE
                    )
                    connection_update = schemas.ConnectionUpdate(status=connection_status)
                    await crud.connection.update(
                        uow.session,
                        db_obj=connection,
                        obj_in=connection_update,
                        ctx=ctx,
                        uow=uow,
                    )

            # Update sync status if it exists
            if source_connection.sync_id:
                sync = await crud.sync.get(uow.session, id=source_connection.sync_id, ctx=ctx)
                if sync:
                    sync_status = (
                        SyncStatus.ACTIVE
                        if status == SourceConnectionStatus.ACTIVE
                        else SyncStatus.INACTIVE
                    )
                    sync_update = schemas.SyncUpdate(status=sync_status)
                    await crud.sync.update(
                        uow.session,
                        db_obj=sync,
                        obj_in=sync_update,
                        ctx=ctx,
                        uow=uow,
                    )

            await uow.commit()
            return source_connection

    async def get_oauth2_authorization_url(
        self,
        source_short_name: str,
        client_id: Optional[str] = None,
    ) -> schemas.OAuth2AuthUrl:
        """Get the OAuth2 authorization URL for a source.

        Args:
            source_short_name: The short name of the source
            client_id: Optional client ID to override the default one

        Returns:
            The OAuth2 authorization URL

        Raises:
            HTTPException: If the source is not found or doesn't support OAuth2
        """
        # Get the settings for this source to generate the URL
        oauth2_settings = await integration_settings.get_by_short_name(source_short_name)
        if not oauth2_settings:
            raise HTTPException(
                status_code=404, detail=f"Settings not found for source: {source_short_name}"
            )

        if oauth2_settings.auth_type not in [
            AuthType.oauth2,
            AuthType.oauth2_with_refresh,
            AuthType.oauth2_with_refresh_rotating,
        ]:
            raise HTTPException(
                status_code=400,
                detail=f"Source {source_short_name} does not support OAuth2 authentication",
            )

        # Generate the authorization URL
        auth_url = await oauth2_service.generate_auth_url(oauth2_settings, client_id)

        # Return as schema
        return schemas.OAuth2AuthUrl(url=auth_url)

    async def create_credential_from_oauth2_code(
        self,
        db: AsyncSession,
        source_short_name: str,
        code: str,
        ctx: ApiContext,
        credential_name: Optional[str] = None,
        credential_description: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> schemas.IntegrationCredentialInDB:
        """Exchange OAuth2 code for token and create integration credentials.

        This method:
        1. Exchanges the authorization code for a token
        2. Validates the token against the auth config class
        3. Creates and stores the integration credential
        4. Returns the stored credential

        Args:
            db: The database session
            source_short_name: The short name of the source
            code: The authorization code to exchange
            ctx: The API context
            credential_name: Optional custom name for the credential
            credential_description: Optional description for the credential
            client_id: Optional client ID to override the default
            client_secret: Optional client secret to override the default

        Returns:
            The created integration credential

        Raises:
            HTTPException: If code exchange fails or validation fails
        """
        try:
            # Get the source information first
            source = await crud.source.get_by_short_name(db, short_name=source_short_name)
            if not source:
                raise HTTPException(
                    status_code=404, detail=f"Source not found: {source_short_name}"
                )

            # Check if auth type is OAuth2
            if not source.auth_type or not source.auth_type.startswith("oauth2"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Source {source_short_name} does not support OAuth2 authentication",
                )

            # Exchange the authorization code for a token
            token_response = await self._exchange_authorization_code_for_token(
                ctx,
                source_short_name=source_short_name,
                code=code,
                client_id=client_id,
                client_secret=client_secret,
            )

            # Convert token response to auth fields
            auth_fields = token_response.model_dump()

            # Add client_id and client_secret to auth_fields if they were provided
            if client_id:
                auth_fields["client_id"] = client_id
            if client_secret:
                auth_fields["client_secret"] = client_secret

            # Validate the auth fields against the auth config class (critical step!)
            validated_auth_fields = await self._validate_auth_fields(
                db=db, source_short_name=source_short_name, auth_fields=auth_fields, ctx=ctx
            )

            # Create the integration credential
            async with UnitOfWork(db) as uow:
                # Encrypt the validated auth fields
                encrypted_credentials = credentials.encrypt(validated_auth_fields)

                # Default name and description if not provided
                name = credential_name or f"{source.name} OAuth2 Credential"
                description = credential_description or f"OAuth2 credentials for {source.name}"

                integration_cred_in = schemas.IntegrationCredentialCreateEncrypted(
                    name=name,
                    description=description,
                    integration_short_name=source_short_name,
                    integration_type=IntegrationType.SOURCE,
                    auth_type=source.auth_type,
                    encrypted_credentials=encrypted_credentials,
                    auth_config_class=source.auth_config_class,
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

        except Exception as e:
            ctx.logger.error(f"Failed to create credential from OAuth2 code: {e}")
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(
                status_code=400, detail=f"Failed to create credential from OAuth2 code: {str(e)}"
            ) from e

    async def _exchange_authorization_code_for_token(
        self,
        ctx: ApiContext,
        source_short_name: str,
        code: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> OAuth2TokenResponse:
        """Exchange an OAuth2 authorization code for a token.

        Args:
            ctx: The API context
            source_short_name: The short name of the source
            code: The authorization code to exchange
            client_id: Optional client ID to override the default
            client_secret: Optional client secret to override the default

        Returns:
            The OAuth2 token response with access token and other details

        Raises:
            HTTPException: If the token exchange fails
        """
        try:
            return await oauth2_service.exchange_authorization_code_for_token(
                ctx=ctx,
                source_short_name=source_short_name,
                code=code,
                client_id=client_id,
                client_secret=client_secret,
            )
        except Exception as e:
            raise HTTPException(
                status_code=400, detail="Failed to exchange authorization code for token"
            ) from e


# Singleton instance
source_connection_service = SourceConnectionService()
