"""Module for sync factory that creates context and orchestrator instances."""

import importlib
import time
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core import credentials
from airweave.core.config import settings
from airweave.core.constants.reserved_ids import RESERVED_TABLE_ENTITY_ID
from airweave.core.exceptions import NotFoundException
from airweave.core.guard_rail_service import GuardRailService
from airweave.core.logging import ContextualLogger, LoggerConfigurator, logger
from airweave.core.sync_cursor_service import sync_cursor_service
from airweave.platform.auth.services import oauth2_service
from airweave.platform.auth_providers._base import BaseAuthProvider
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.embedding_models._base import BaseEmbeddingModel
from airweave.platform.embedding_models.bm25_text2vec import BM25Text2Vec
from airweave.platform.embedding_models.local_text2vec import LocalText2Vec
from airweave.platform.embedding_models.openai_text2vec import OpenAIText2Vec
from airweave.platform.entities._base import BaseEntity
from airweave.platform.locator import resource_locator
from airweave.platform.sources._base import BaseSource
from airweave.platform.sync.context import SyncContext
from airweave.platform.sync.cursor import SyncCursor
from airweave.platform.sync.entity_processor import EntityProcessor
from airweave.platform.sync.orchestrator import SyncOrchestrator
from airweave.platform.sync.pubsub import SyncEntityStateTracker, SyncProgress
from airweave.platform.sync.router import SyncDAGRouter
from airweave.platform.sync.token_manager import TokenManager
from airweave.platform.sync.worker_pool import AsyncWorkerPool


class SyncFactory:
    """Factory for sync orchestrator."""

    @classmethod
    async def create_orchestrator(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        dag: schemas.SyncDag,
        collection: schemas.Collection,
        source_connection: schemas.SourceConnection,
        ctx: ApiContext,
        access_token: Optional[str] = None,
        max_workers: int = None,
        force_full_sync: bool = False,
    ) -> SyncOrchestrator:
        """Create a dedicated orchestrator instance for a sync run.

        This method creates all necessary components for a sync run, including the
        context and a dedicated orchestrator instance for concurrent execution.

        Args:
            db: Database session
            sync: The sync configuration
            sync_job: The sync job
            dag: The DAG for the sync
            collection: The collection to sync to
            source_connection: The source connection
            ctx: The API context
            access_token: Optional token to use instead of stored credentials
            max_workers: Maximum number of concurrent workers (default: from settings)
            force_full_sync: If True, forces a full sync with orphaned entity deletion

        Returns:
            A dedicated SyncOrchestrator instance
        """
        # Use configured value if max_workers not specified
        if max_workers is None:
            max_workers = settings.SYNC_MAX_WORKERS
            logger.debug(f"Using configured max_workers: {max_workers}")

        # Track initialization timing
        init_start = time.time()

        # Create sync context
        logger.info("Creating sync context...")
        context_start = time.time()
        sync_context = await cls._create_sync_context(
            db=db,
            sync=sync,
            sync_job=sync_job,
            dag=dag,
            collection=collection,
            source_connection=source_connection,
            ctx=ctx,
            access_token=access_token,
            force_full_sync=force_full_sync,
        )
        logger.debug(f"Sync context created in {time.time() - context_start:.2f}s")

        # CRITICAL FIX: Initialize transformer cache to eliminate 1.5s database lookups
        cache_start = time.time()
        await sync_context.router.initialize_transformer_cache(db)
        logger.debug(f"Transformer cache initialized in {time.time() - cache_start:.2f}s")

        # Create entity processor
        entity_processor = EntityProcessor()

        # Create worker pool
        pool_start = time.time()
        worker_pool = AsyncWorkerPool(max_workers=max_workers, logger=sync_context.logger)
        sync_context.logger.debug(f"Worker pool created in {time.time() - pool_start:.2f}s")

        # Create dedicated orchestrator instance
        orchestrator = SyncOrchestrator(
            entity_processor=entity_processor,
            worker_pool=worker_pool,
            sync_context=sync_context,
        )

        # Initialize entity tracking
        entity_processor.initialize_tracking(sync_context)

        logger.info(f"Total orchestrator initialization took {time.time() - init_start:.2f}s")

        return orchestrator

    @classmethod
    async def _create_sync_context(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        dag: schemas.SyncDag,
        collection: schemas.Collection,
        source_connection: schemas.SourceConnection,
        ctx: ApiContext,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
    ) -> SyncContext:
        """Create a sync context.

        Args:
            db: Database session
            sync: The sync configuration
            sync_job: The sync job
            dag: The DAG for the sync
            collection: The collection to sync to
            source_connection: The source connection
            ctx: The API context
            access_token: Optional token to use instead of stored credentials
            force_full_sync: If True, forces a full sync with orphaned entity deletion

        Returns:
            SyncContext object with all required components
        """
        # Get source connection data first to access white_label_id safely
        source_connection_data = await cls._get_source_connection_data(db, sync, ctx)

        # Create a contextualized logger with all job metadata
        logger = LoggerConfigurator.configure_logger(
            "airweave.platform.sync",
            dimensions={
                "sync_id": str(sync.id),
                "sync_job_id": str(sync_job.id),
                "organization_id": str(ctx.organization.id),
                "source_connection_id": str(source_connection_data["connection_id"]),
                "collection_readable_id": str(collection.readable_id),
                "organization_name": ctx.organization.name,
                "scheduled": str(sync_job.scheduled),
            },
        )

        # Fetch white label if set in sync using pre-fetched white_label_id
        white_label = None
        if source_connection_data["white_label_id"]:
            white_label = await crud.white_label.get(
                db, id=source_connection_data["white_label_id"], ctx=ctx
            )

        source = await cls._create_source_instance_with_data(
            db=db,
            source_connection_data=source_connection_data,
            ctx=ctx,
            white_label=white_label,
            access_token=access_token,
            logger=logger,  # Pass the contextual logger
        )
        embedding_model = cls._get_embedding_model(collection=collection, logger=logger)
        keyword_indexing_model = cls._get_keyword_indexing_model(logger=logger)
        destinations = await cls._create_destination_instances(
            db=db,
            sync=sync,
            collection=collection,
            ctx=ctx,
            logger=logger,
        )
        transformers = await cls._get_transformer_callables(db=db, sync=sync)
        entity_map = await cls._get_entity_definition_map(db=db)

        progress = SyncProgress(sync_job.id, logger=logger)

        # NEW: Load initial entity counts from database for state tracking
        initial_counts = await crud.entity_count.get_counts_per_sync_and_type(db, sync.id)

        logger.info(f"🔢 Loaded initial entity counts: {len(initial_counts)} entity types")

        # Log the initial counts for debugging
        for count in initial_counts:
            logger.debug(f"  - {count.entity_definition_name}: {count.count} entities")

        # NEW: Create state-aware tracker (parallel to existing progress)
        entity_state_tracker = SyncEntityStateTracker(
            job_id=sync_job.id, sync_id=sync.id, initial_counts=initial_counts, logger=logger
        )

        logger.info(
            f"✅ Created SyncEntityStateTracker for job {sync_job.id}, "
            f"channel: sync_job_state:{sync_job.id}"
        )

        router = SyncDAGRouter(dag, entity_map, logger=logger)

        logger.info("Sync context created")

        # Create GuardRailService with contextual logger
        guard_rail = GuardRailService(
            organization_id=ctx.organization.id,
            logger=logger.with_context(component="guardrail"),
        )

        # Load existing cursor data and field from database
        # IMPORTANT: When force_full_sync is True (daily cleanup), we intentionally
        # skip loading cursor DATA (but keep the field) to force a full sync.
        # This ensures we see ALL entities in the source, not just changed ones,
        # for accurate orphaned entity detection. We still track and save cursor
        # values during the sync for the next incremental sync.

        # Always load the cursor field (needed for tracking)
        cursor_field = await sync_cursor_service.get_cursor_field(db=db, sync_id=sync.id, ctx=ctx)

        if force_full_sync:
            logger.info(
                "🔄 FORCE FULL SYNC: Skipping cursor data to ensure all entities are fetched "
                "for accurate orphaned entity cleanup. Will still track cursor for next sync."
            )
            cursor_data = None  # Force full sync by not providing previous cursor data
        else:
            # Normal incremental sync - load cursor data
            cursor_data = await sync_cursor_service.get_cursor_data(db=db, sync_id=sync.id, ctx=ctx)
            if cursor_data:
                logger.info(f"📊 Incremental sync: Using cursor data for {len(cursor_data)} tables")

        cursor = SyncCursor(sync_id=sync.id, cursor_data=cursor_data, cursor_field=cursor_field)

        # Create sync context
        sync_context = SyncContext(
            source=source,
            destinations=destinations,
            embedding_model=embedding_model,
            keyword_indexing_model=keyword_indexing_model,
            transformers=transformers,
            sync=sync,
            sync_job=sync_job,
            dag=dag,
            collection=collection,
            source_connection=source_connection,
            progress=progress,
            entity_state_tracker=entity_state_tracker,
            cursor=cursor,
            router=router,
            entity_map=entity_map,
            ctx=ctx,
            logger=logger,
            guard_rail=guard_rail,
            white_label=white_label,
            force_full_sync=force_full_sync,
        )

        # Set cursor on source so it can access cursor data
        source.set_cursor(cursor)

        return sync_context

    @classmethod
    async def _create_source_instance(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        logger: ContextualLogger,
        ctx: ApiContext,
        white_label: Optional[schemas.WhiteLabel] = None,
        access_token: Optional[str] = None,
    ) -> BaseSource:
        """Create and configure the source instance based on authentication type."""
        # Get source connection and model
        source_connection_data = await cls._get_source_connection_data(db, sync, ctx)

        return await cls._create_source_instance_with_data(
            db, source_connection_data, ctx, white_label, access_token, logger
        )

    @classmethod
    async def _create_source_instance_with_data(
        cls,
        db: AsyncSession,
        source_connection_data: dict,
        ctx: ApiContext,
        logger: ContextualLogger,
        white_label: Optional[schemas.WhiteLabel] = None,
        access_token: Optional[str] = None,
    ) -> BaseSource:
        """Create and configure the source instance using pre-fetched connection data."""
        # Step 1: Create auth provider instance if this connection uses one
        auth_provider_instance = None
        readable_auth_provider_id = source_connection_data.get("readable_auth_provider_id")
        auth_provider_config = source_connection_data.get("auth_provider_config")

        if readable_auth_provider_id and auth_provider_config:
            logger.info("Creating auth provider instance for source connection...")
            auth_provider_instance = await cls._create_auth_provider_instance(
                db=db,
                readable_auth_provider_id=readable_auth_provider_id,
                auth_provider_config=auth_provider_config,
                ctx=ctx,
                logger=logger,
            )

        # Step 2: Get credentials from appropriate source
        source_credentials = await cls._get_source_credentials(
            db=db,
            source_connection_data=source_connection_data,
            ctx=ctx,
            white_label=white_label,
            access_token=access_token,
            auth_provider_instance=auth_provider_instance,
        )

        # Step 2.5: Convert credentials to auth config object if needed
        # When using auth providers, credentials come as a dict, but some sources
        # expect an auth config object (e.g., Stripe expects StripeAuthConfig)
        auth_config_class_name = source_connection_data.get("auth_config_class")
        if auth_config_class_name and isinstance(source_credentials, dict):
            # Source has an auth config class and credentials are a dict
            # This happens with auth providers - convert dict to config object
            try:
                auth_config_class = resource_locator.get_auth_config(auth_config_class_name)
                source_credentials = auth_config_class.model_validate(source_credentials)
                logger.info(
                    f"Converted auth provider credentials to {auth_config_class_name} object"
                )
            except Exception as e:
                logger.error(f"Failed to convert credentials to auth config object: {e}")
                raise

        # Step 3: Create the source instance with actual credentials
        source = await source_connection_data["source_class"].create(
            source_credentials, config=source_connection_data["config_fields"]
        )

        # Step 4: Configure source with logger
        if hasattr(source, "set_logger"):
            source.set_logger(logger)

        # Step 4.1: Pass sync identifiers to the source for scoped helpers
        try:
            organization_id = ctx.organization.id
            source_connection_obj = source_connection_data.get("source_connection_obj")
            if hasattr(source, "set_sync_identifiers") and source_connection_obj:
                source.set_sync_identifiers(
                    organization_id=str(organization_id),
                    source_connection_id=str(source_connection_obj.id),
                )
        except Exception:
            # Non-fatal: older sources may ignore this
            pass

        # Step 5: Setup token manager if needed
        # The _setup_token_manager method will check if this source needs a token manager
        # based on whether its auth config inherits from OAuth2AuthConfig
        try:
            await cls._setup_token_manager(
                db=db,
                source=source,
                source_connection_data=source_connection_data,
                source_credentials=source_credentials,
                ctx=ctx,
                white_label=white_label,
                logger=logger,
                auth_provider_instance=auth_provider_instance,
            )
        except Exception as e:
            logger.error(
                f"Failed to setup token manager for source "
                f"'{source_connection_data['short_name']}': {e}"
            )
            # Don't fail source creation if token manager setup fails
            # The source can still work, just without automatic token refresh

        return source

    @classmethod
    async def _get_source_connection_data(
        cls, db: AsyncSession, sync: schemas.Sync, ctx: ApiContext
    ) -> dict:
        """Get source connection and model data."""
        # 1. Get SourceConnection first (has most of our data)
        source_connection_obj = await crud.source_connection.get_by_sync_id(
            db, sync_id=sync.id, ctx=ctx
        )
        if not source_connection_obj:
            raise NotFoundException("Source connection record not found")

        # 2. Get Connection only to access integration_credential_id
        connection = await crud.connection.get(db, source_connection_obj.connection_id, ctx)
        if not connection:
            raise NotFoundException("Connection not found")

        # 3. Get Source model using short_name from SourceConnection
        source_model = await crud.source.get_by_short_name(db, source_connection_obj.short_name)
        if not source_model:
            raise NotFoundException(f"Source not found: {source_connection_obj.short_name}")

        # Get all fields from the RIGHT places:
        config_fields = source_connection_obj.config_fields or {}  # From SourceConnection

        # Pre-fetch to avoid lazy loading - convert to pure Python types
        auth_config_class = source_model.auth_config_class
        # Convert SQLAlchemy values to clean Python types to avoid lazy loading
        short_name = str(source_connection_obj.short_name)  # From SourceConnection
        white_label_id = (
            UUID(str(source_connection_obj.white_label_id))
            if source_connection_obj.white_label_id
            else None
        )
        connection_id = UUID(str(connection.id))

        # Check if this connection uses an auth provider
        readable_auth_provider_id = getattr(
            source_connection_obj, "readable_auth_provider_id", None
        )

        # For auth provider connections, integration_credential_id will be None
        # For regular connections, integration_credential_id must be set
        if not readable_auth_provider_id and not connection.integration_credential_id:
            raise NotFoundException(f"Connection {connection_id} has no integration credential")

        integration_credential_id = (
            UUID(str(connection.integration_credential_id))
            if connection.integration_credential_id
            else None
        )

        source_class = resource_locator.get_source(source_model)

        return {
            "source_connection_obj": source_connection_obj,  # The main entity
            "connection": connection,  # Just for credential access
            "source_model": source_model,
            "source_class": source_class,
            "config_fields": config_fields,  # From SourceConnection
            "white_label_id": white_label_id,  # From SourceConnection
            "short_name": short_name,  # From SourceConnection
            "auth_config_class": auth_config_class,
            "connection_id": connection_id,
            "integration_credential_id": integration_credential_id,  # From Connection
            "readable_auth_provider_id": getattr(
                source_connection_obj, "readable_auth_provider_id", None
            ),
            "auth_provider_config": getattr(source_connection_obj, "auth_provider_config", None),
        }

    @classmethod
    async def _create_auth_provider_instance(
        cls,
        db: AsyncSession,
        readable_auth_provider_id: str,
        auth_provider_config: Dict[str, Any],
        ctx: ApiContext,
        logger: ContextualLogger,
    ) -> Any:
        """Create an auth provider instance from readable_id.

        Args:
            db: Database session
            readable_auth_provider_id: The readable ID of the auth provider connection
            auth_provider_config: Configuration for the auth provider
            ctx: The API context
            logger: Optional logger to set on the auth provider

        Returns:
            An instance of the auth provider

        Raises:
            NotFoundException: If auth provider connection not found
        """
        # 1. Get the auth provider connection by readable_id
        auth_provider_connection = await crud.connection.get_by_readable_id(
            db, readable_id=readable_auth_provider_id, ctx=ctx
        )
        if not auth_provider_connection:
            raise NotFoundException(
                f"Auth provider connection with readable_id '{readable_auth_provider_id}' not found"
            )

        # 2. Get the integration credential
        if not auth_provider_connection.integration_credential_id:
            raise NotFoundException(
                f"Auth provider connection '{readable_auth_provider_id}' "
                f"has no integration credential"
            )

        credential = await crud.integration_credential.get(
            db, auth_provider_connection.integration_credential_id, ctx
        )
        if not credential:
            raise NotFoundException("Auth provider integration credential not found")

        # 3. Decrypt the credentials
        decrypted_credentials = credentials.decrypt(credential.encrypted_credentials)

        # 4. Get the auth provider model
        auth_provider_model = await crud.auth_provider.get_by_short_name(
            db, short_name=auth_provider_connection.short_name
        )
        if not auth_provider_model:
            raise NotFoundException(
                f"Auth provider model not found for '{auth_provider_connection.short_name}'"
            )

        # 5. Create the auth provider instance
        auth_provider_class = resource_locator.get_auth_provider(auth_provider_model)
        auth_provider_instance = await auth_provider_class.create(
            credentials=decrypted_credentials,
            config=auth_provider_config,
        )

        # 6. Set logger if provided
        if hasattr(auth_provider_instance, "set_logger"):
            auth_provider_instance.set_logger(logger)

            logger.info(
                f"Created auth provider instance: {auth_provider_instance.__class__.__name__} "
                f"for readable_id: {readable_auth_provider_id}"
            )

        return auth_provider_instance

    @classmethod
    async def _get_source_credentials(
        cls,
        db: AsyncSession,
        source_connection_data: dict,
        ctx: ApiContext,
        white_label: Optional[schemas.WhiteLabel],
        access_token: Optional[str],
        auth_provider_instance: Optional[Any] = None,
    ) -> any:
        """Get source credentials from the appropriate source.

        Priority order:
        1. Direct token injection (if access_token provided)
        2. Auth provider instance (if available)
        3. Database credentials (with OAuth refresh if applicable)

        Returns:
            Tuple of (access_token, credentials) where credentials can be:
            - A string token for simple auth
            - A dict with auth fields
            - An auth config object
        """
        # Case 1: Direct token injection - highest priority
        if access_token:
            logger.debug("Using directly injected access token")
            return access_token

        # Case 2: Auth provider credentials
        if auth_provider_instance:
            logger.debug("Getting credentials from auth provider instance")
            return await cls._get_credentials_from_auth_provider(
                auth_provider_instance=auth_provider_instance,
                source_connection_data=source_connection_data,
            )

        # Case 3: Database credentials (regular flow)
        integration_credential_id = source_connection_data["integration_credential_id"]
        if not integration_credential_id:
            raise NotFoundException("Source connection has no integration credential")

        credential = await cls._get_integration_credential(db, integration_credential_id, ctx)
        decrypted_credential = credentials.decrypt(credential.encrypted_credentials)

        # Check if we need to handle auth config (e.g., OAuth refresh)
        auth_config_class = source_connection_data["auth_config_class"]
        if auth_config_class:
            return await cls._handle_auth_config_credentials(
                db=db,
                source_connection_data=source_connection_data,
                decrypted_credential=decrypted_credential,
                ctx=ctx,
                connection_id=source_connection_data["connection_id"],
                white_label=white_label,
            )

        # Simple credentials - no token extraction needed
        return decrypted_credential

    @classmethod
    async def _get_credentials_from_auth_provider(
        cls,
        auth_provider_instance: BaseAuthProvider,
        source_connection_data: dict,
    ) -> any:
        """Get credentials from an auth provider instance."""
        source_short_name = source_connection_data["short_name"]

        # Get the runtime auth fields required by the source (excluding BYOC fields)
        # Import here to avoid circular imports
        from airweave.core.auth_provider_service import auth_provider_service

        # Create a temporary db session for this query
        from airweave.db.session import get_db_context

        async with get_db_context() as db:
            source_auth_config_fields = (
                await auth_provider_service.get_runtime_auth_fields_for_source(
                    db, source_short_name
                )
            )

        # Get fresh credentials from auth provider
        fresh_credentials = await auth_provider_instance.get_creds_for_source(
            source_short_name=source_short_name,
            source_auth_config_fields=source_auth_config_fields,
        )

        logger.debug(
            f"Successfully obtained credentials from auth provider for source '{source_short_name}'"
        )

        return fresh_credentials

    @classmethod
    async def _handle_auth_config_credentials(
        cls,
        db: AsyncSession,
        source_connection_data: dict,
        decrypted_credential: dict,
        ctx: ApiContext,
        connection_id: UUID,
        white_label: Optional[schemas.WhiteLabel],
    ) -> any:
        """Handle credentials that require auth configuration."""
        # Use pre-fetched auth_config_class to avoid SQLAlchemy lazy loading issues
        auth_config_class = source_connection_data["auth_config_class"]
        short_name = source_connection_data["short_name"]

        auth_config = resource_locator.get_auth_config(auth_config_class)
        source_credentials = auth_config.model_validate(decrypted_credential)

        # Original OAuth refresh logic for non-auth-provider sources
        # If the source_credential has a refresh token, exchange it for an access token
        if hasattr(source_credentials, "refresh_token") and source_credentials.refresh_token:
            oauth2_response = await oauth2_service.refresh_access_token(
                db,
                short_name,
                ctx,
                connection_id,
                decrypted_credential,
                white_label,
            )
            # Just use the access token
            return oauth2_response.access_token

        return source_credentials

    @classmethod
    async def _configure_source_instance(
        cls,
        db: AsyncSession,
        source: BaseSource,
        source_connection_data: dict,
        ctx: ApiContext,
        white_label: Optional[schemas.WhiteLabel],
        final_access_token: Optional[str],
        logger: ContextualLogger,
    ) -> None:
        """Configure source instance with logger and token manager."""
        # Set contextual logger
        source.set_logger(logger)

        # Create and set token manager for OAuth sources
        if hasattr(source, "set_token_manager") and final_access_token:
            await cls._setup_token_manager(
                db,
                source,
                source_connection_data,
                ctx,
                white_label,
                final_access_token,
                logger,
            )

    @classmethod
    async def _setup_token_manager(
        cls,
        db: AsyncSession,
        source: BaseSource,
        source_connection_data: dict,
        source_credentials: any,
        ctx: ApiContext,
        white_label: Optional[schemas.WhiteLabel],
        logger: ContextualLogger,
        auth_provider_instance: Optional[BaseAuthProvider] = None,
    ) -> None:
        """Set up token manager for OAuth sources."""
        short_name = source_connection_data["short_name"]
        auth_config_class_name = source_connection_data.get("auth_config_class")

        # Only create token manager for sources that use OAuth2AuthConfig or its subclasses
        should_create_token_manager = False

        if auth_config_class_name:
            try:
                # Get the auth config class
                auth_config_class = resource_locator.get_auth_config(auth_config_class_name)

                # Check if it's a subclass of OAuth2AuthConfig
                from airweave.platform.configs.auth import OAuth2AuthConfig

                if issubclass(auth_config_class, OAuth2AuthConfig):
                    should_create_token_manager = True
            except Exception as e:
                logger.warning(f"Could not check auth config class for {short_name}: {str(e)}")

        if should_create_token_manager:
            # Create a minimal connection object with only the fields needed by TokenManager
            # Use pre-fetched IDs to avoid SQLAlchemy lazy loading issues
            minimal_source_connection = type(
                "SourceConnection",
                (),
                {
                    "id": source_connection_data["connection_id"],
                    "integration_credential_id": source_connection_data[
                        "integration_credential_id"
                    ],
                },
            )()

            token_manager = TokenManager(
                db=db,
                source_short_name=short_name,
                source_connection=minimal_source_connection,
                ctx=ctx,
                initial_credentials=source_credentials,
                white_label=white_label,
                is_direct_injection=False,  # TokenManager will determine this internally
                logger_instance=logger,
                auth_provider_instance=auth_provider_instance,
            )
            source.set_token_manager(token_manager)

            logger.info(
                f"Token manager initialized for OAuth source {short_name} "
                f"(auth_provider: {'Yes' if auth_provider_instance else 'None'})"
            )
        else:
            logger.debug(
                f"Skipping token manager for {short_name} - "
                "not an OAuth source or no access_token in credentials"
            )

    @classmethod
    async def _get_integration_credential(
        cls,
        db: AsyncSession,
        integration_credential_id: UUID,
        ctx: ApiContext,
    ) -> schemas.IntegrationCredential:
        """Get integration credential."""
        credential = await crud.integration_credential.get(db, integration_credential_id, ctx)
        if not credential:
            raise NotFoundException("Source integration credential not found")
        return credential

    @classmethod
    def _get_embedding_model(cls, collection: schemas.Collection, logger: ContextualLogger) -> BaseEmbeddingModel:
        """Get embedding model instance based on collection's vector size.

        Args:
            collection: The collection to get embedding model for
            logger: The logger to use

        Returns:
            BaseEmbeddingModel: The embedding model to use
        """
        from airweave.core.collection_service import get_embedding_model_for_collection
        
        return get_embedding_model_for_collection(collection, logger)

    @classmethod
    def _get_keyword_indexing_model(cls, logger: ContextualLogger) -> BaseEmbeddingModel:
        """Get keyword indexing model instance."""
        return BM25Text2Vec(logger=logger)

    @classmethod
    async def _create_destination_instances(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        collection: schemas.Collection,
        ctx: ApiContext,
        logger: ContextualLogger,
    ) -> list[BaseDestination]:
        """Create destination instances.

        Args:
        -----
            db (AsyncSession): The database session
            sync (schemas.Sync): The sync object
            collection (schemas.Collection): The collection object
            ctx (ApiContext): The API context
            logger (ContextualLogger): The contextual logger with sync metadata

        Returns:
        --------
            list[BaseDestination]: A list of destination instances
        """
        destination_connection_id = sync.destination_connection_ids[0]

        destination_connection = await crud.connection.get(db, destination_connection_id, ctx)
        if not destination_connection:
            raise NotFoundException(
                (
                    f"Destination connection not found for organization "
                    f"{ctx.organization.id}"
                    f" and connection id {destination_connection_id}"
                )
            )
        destination_model = await crud.destination.get_by_short_name(
            db, destination_connection.short_name
        )
        destination_schema = schemas.Destination.model_validate(destination_model)
        if not destination_model:
            raise NotFoundException(
                f"Destination not found for connection {destination_connection.short_name}"
            )

        destination_class = resource_locator.get_destination(destination_schema)
        destination = await destination_class.create(collection_id=collection.id, logger=ctx.logger)

        # Set contextual logger on destination
        if hasattr(destination, "set_logger"):
            destination.set_logger(logger)
            logger.debug(
                f"Set contextual logger on destination: {destination_connection.short_name}"
            )

        return [destination]

    @classmethod
    async def _get_transformer_callables(
        cls, db: AsyncSession, sync: schemas.Sync
    ) -> dict[str, callable]:
        """Get transformers instance."""
        transformers = {}

        transformer_functions = await crud.transformer.get_all(db)
        for transformer in transformer_functions:
            transformers[transformer.method_name] = resource_locator.get_transformer(transformer)
        return transformers

    @classmethod
    async def _get_entity_definition_map(cls, db: AsyncSession) -> dict[type[BaseEntity], UUID]:
        """Get entity definition map.

        Map entity class to entity definition id.

        Example key-value pair:
            <class 'airweave.platform.entities.trello.TrelloBoard'>: entity_definition_id
        """
        entity_definitions = await crud.entity_definition.get_all(db)

        entity_definition_map = {}
        for entity_definition in entity_definitions:
            if entity_definition.id == RESERVED_TABLE_ENTITY_ID:
                continue
            full_module_name = f"airweave.platform.entities.{entity_definition.module_name}"
            module = importlib.import_module(full_module_name)
            entity_class = getattr(module, entity_definition.class_name)
            entity_definition_map[entity_class] = entity_definition.id

        return entity_definition_map
