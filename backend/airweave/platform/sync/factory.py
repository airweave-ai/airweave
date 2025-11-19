"""Module for sync factory that creates context and orchestrator instances."""

import importlib
import time
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core import credentials
from airweave.core.config import settings
from airweave.core.constants.reserved_ids import NATIVE_QDRANT_UUID, RESERVED_TABLE_ENTITY_ID
from airweave.core.exceptions import NotFoundException
from airweave.core.guard_rail_service import GuardRailService
from airweave.core.logging import ContextualLogger, LoggerConfigurator, logger
from airweave.core.sync_cursor_service import sync_cursor_service
from airweave.db.init_db_native import init_db_with_entity_definitions
from airweave.platform.auth_providers._base import BaseAuthProvider
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.entities._base import BaseEntity
from airweave.platform.locator import resource_locator
from airweave.platform.sources._base import BaseSource
from airweave.platform.sync.context import SyncContext
from airweave.platform.sync.cursor import SyncCursor
from airweave.platform.sync.entity_pipeline import EntityPipeline
from airweave.platform.sync.orchestrator import SyncOrchestrator
from airweave.platform.sync.pubsub import SyncEntityStateTracker, SyncProgress
from airweave.platform.sync.stream import AsyncSourceStream
from airweave.platform.sync.token_manager import TokenManager
from airweave.platform.sync.worker_pool import AsyncWorkerPool
from airweave.platform.utils.source_factory_utils import (
    get_auth_configuration,
    process_credentials_for_source,
)


class SyncFactory:
    """Factory for sync orchestrator."""

    @classmethod
    async def create_orchestrator(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.Collection,
        connection: schemas.Connection,  # Passed but unused - we load from DB
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
            collection: The collection to sync to
            connection: The connection (unused - we load source connection from DB)
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
            collection=collection,
            connection=connection,  # Unused parameter
            ctx=ctx,
            access_token=access_token,
            force_full_sync=force_full_sync,
        )
        logger.debug(f"Sync context created in {time.time() - context_start:.2f}s")

        # Create entity pipeline
        entity_pipeline = EntityPipeline()

        # Create worker pool
        worker_pool = AsyncWorkerPool(max_workers=max_workers, logger=sync_context.logger)

        stream = AsyncSourceStream(
            source_generator=sync_context.source.generate_entities(),
            queue_size=10000,  # TODO: make this configurable
            logger=sync_context.logger,
        )

        # Create dedicated orchestrator instance with all components
        orchestrator = SyncOrchestrator(
            entity_pipeline=entity_pipeline,
            worker_pool=worker_pool,
            stream=stream,
            sync_context=sync_context,
        )

        logger.info(f"Total orchestrator initialization took {time.time() - init_start:.2f}s")

        return orchestrator

    @classmethod
    async def _create_sync_context(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.Collection,
        connection: schemas.Connection,
        ctx: ApiContext,
        access_token: Optional[str] = None,
        force_full_sync: bool = False,
    ) -> SyncContext:
        """Create a sync context.

        Args:
            db: Database session
            sync: The sync configuration
            sync_job: The sync job
            collection: The collection to sync to
            connection: The connection (unused - we load source connection from DB)
            ctx: The API context
            access_token: Optional token to use instead of stored credentials
            force_full_sync: If True, forces a full sync with orphaned entity deletion

        Returns:
            SyncContext object with all required components
        """
        # Get source connection data first (includes source class with cursor schema)
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

        source = await cls._create_source_instance_with_data(
            db=db,
            source_connection_data=source_connection_data,
            ctx=ctx,
            access_token=access_token,
            logger=logger,  # Pass the contextual logger
            sync_job=sync_job,  # Pass sync_job for file downloader temp directory setup
        )
        destinations = await cls._create_destination_instances(
            db=db,
            sync=sync,
            collection=collection,
            ctx=ctx,
            logger=logger,
        )
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

        logger.info("Sync context created")

        # Create GuardRailService with contextual logger
        guard_rail = GuardRailService(
            organization_id=ctx.organization.id,
            logger=logger.with_context(component="guardrail"),
        )

        # Load existing cursor data from database
        # IMPORTANT: When force_full_sync is True (daily cleanup), we intentionally
        # skip loading cursor DATA to force a full sync.
        # This ensures we see ALL entities in the source, not just changed ones,
        # for accurate orphaned entity detection. We still track and save cursor
        # values during the sync for the next incremental sync.

        # Get cursor schema from source class (direct reference, no string lookup!)
        cursor_schema = None
        source_class = source_connection_data["source_class"]
        if hasattr(source_class, "_cursor_class") and source_class._cursor_class:
            cursor_schema = source_class._cursor_class  # Direct class reference
            logger.debug(f"Source has typed cursor: {cursor_schema.__name__}")

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
                logger.info(f"📊 Incremental sync: Using cursor data with {len(cursor_data)} keys")

        # Create typed cursor (no locator needed - direct class reference!)
        cursor = SyncCursor(
            sync_id=sync.id,
            cursor_schema=cursor_schema,
            cursor_data=cursor_data,
        )

        # Precompute destination keyword-index capability once
        has_keyword_index = False
        try:
            import asyncio as _asyncio

            if destinations:
                has_keyword_index = any(
                    await _asyncio.gather(*[dest.has_keyword_index() for dest in destinations])
                )
        except Exception as _e:
            logger.warning(f"Failed to precompute keyword index capability on destinations: {_e}")
            has_keyword_index = False

        # Create sync context
        sync_context = SyncContext(
            source=source,
            destinations=destinations,
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            connection=connection,  # Unused parameter
            progress=progress,
            entity_state_tracker=entity_state_tracker,
            cursor=cursor,
            entity_map=entity_map,
            ctx=ctx,
            logger=logger,
            guard_rail=guard_rail,
            force_full_sync=force_full_sync,
            has_keyword_index=has_keyword_index,
        )

        # Set cursor on source so it can access cursor data
        source.set_cursor(cursor)

        return sync_context

    @classmethod
    async def _create_source_instance_with_data(
        cls,
        db: AsyncSession,
        source_connection_data: dict,
        ctx: ApiContext,
        logger: ContextualLogger,
        access_token: Optional[str] = None,
        sync_job: Optional[Any] = None,
    ) -> BaseSource:
        """Create and configure the source instance using pre-fetched connection data."""
        # Get auth configuration (credentials + proxy setup if needed)
        auth_config = await get_auth_configuration(
            db=db,
            source_connection_data=source_connection_data,
            ctx=ctx,
            logger=logger,
            access_token=access_token,
        )

        # Process credentials for source consumption
        source_credentials = await process_credentials_for_source(
            raw_credentials=auth_config["credentials"],
            source_connection_data=source_connection_data,
            logger=logger,
        )

        # Create the source instance with processed credentials
        source = await source_connection_data["source_class"].create(
            source_credentials, config=source_connection_data["config_fields"]
        )

        # Configure source with logger
        if hasattr(source, "set_logger"):
            source.set_logger(logger)

        # Set HTTP client factory if proxy is needed
        if auth_config.get("http_client_factory"):
            source.set_http_client_factory(auth_config["http_client_factory"])

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

        # Setup token manager for OAuth sources (if applicable)
        # Skip for:
        # 1. Direct token injection (when access_token parameter was explicitly passed)
        # 2. Proxy mode (PipedreamProxyClient or other proxies manage tokens internally)
        from airweave.platform.auth_providers.auth_result import AuthProviderMode

        auth_mode = auth_config.get("auth_mode")
        auth_provider_instance = auth_config.get("auth_provider_instance")

        # Check if we should skip TokenManager
        is_direct_token_injection = access_token is not None
        is_proxy_mode = auth_mode == AuthProviderMode.PROXY

        if not is_direct_token_injection and not is_proxy_mode:
            try:
                await cls._setup_token_manager(
                    db=db,
                    source=source,
                    source_connection_data=source_connection_data,
                    source_credentials=auth_config["credentials"],
                    ctx=ctx,
                    logger=logger,
                    auth_provider_instance=auth_provider_instance,
                )
            except Exception as e:
                logger.error(
                    f"Failed to setup token manager for source "
                    f"'{source_connection_data['short_name']}': {e}"
                )
                # Don't fail source creation if token manager setup fails
        elif is_proxy_mode:
            logger.info(
                f"⏭️ Skipping token manager for {source_connection_data['short_name']} - "
                f"proxy mode (PipedreamProxyClient manages tokens internally)"
            )
        else:
            logger.debug(
                f"⏭️ Skipping token manager for {source_connection_data['short_name']} - "
                f"direct token injection"
            )

        # Setup file downloader for file-based sources
        cls._setup_file_downloader(source, sync_job, logger)

        # Wrap HTTP client with AirweaveHttpClient for rate limiting
        # This wraps whatever client is currently set (httpx or Pipedream proxy)
        from airweave.platform.utils.source_factory_utils import wrap_source_with_airweave_client

        wrap_source_with_airweave_client(
            source=source,
            source_short_name=source_connection_data["short_name"],
            source_connection_id=source_connection_data["source_connection_obj"].id,
            ctx=ctx,
            logger=logger,
        )

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
            raise NotFoundException(
                f"Source connection record not found for sync {sync.id}. "
                f"This typically occurs when a source connection is deleted while a "
                f"scheduled workflow is queued. The workflow should self-destruct and "
                f"clean up orphaned schedules."
            )

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
    def _setup_file_downloader(
        cls, source: BaseSource, sync_job: Optional[Any], logger: ContextualLogger
    ) -> None:
        """Setup file downloader for file-based sources.

        All sources get a file downloader (even API-only sources) since BaseSource
        provides set_file_downloader(). Sources that don't download files simply
        won't use it.

        Args:
            source: Source instance to configure
            sync_job: Sync job for temp directory organization (required)
            logger: Logger for diagnostics

        Raises:
            ValueError: If sync_job is None (programming error)
        """
        from airweave.platform.downloader import FileDownloadService

        # Require sync_job - we're always in sync context when this is called
        if not sync_job or not hasattr(sync_job, "id"):
            raise ValueError(
                "sync_job is required for file downloader initialization. "
                "This method should only be called from create_orchestrator() "
                "where sync_job exists."
            )

        file_downloader = FileDownloadService(sync_job_id=str(sync_job.id))
        source.set_file_downloader(file_downloader)
        logger.debug(
            f"File downloader configured for {source.__class__.__name__} "
            f"(sync_job_id: {sync_job.id})"
        )

    @classmethod
    async def _setup_token_manager(
        cls,
        db: AsyncSession,
        source: BaseSource,
        source_connection_data: dict,
        source_credentials: any,
        ctx: ApiContext,
        logger: ContextualLogger,
        auth_provider_instance: Optional[BaseAuthProvider] = None,
    ) -> None:
        """Set up token manager for OAuth sources."""
        short_name = source_connection_data["short_name"]
        source_model = source_connection_data.get("source_model")

        # Determine if we should create a token manager based on oauth_type
        should_create_token_manager = False

        if source_model and hasattr(source_model, "oauth_type") and source_model.oauth_type:
            # Import OAuthType enum
            from airweave.schemas.source_connection import OAuthType

            # Only create token manager for sources that support token refresh
            if source_model.oauth_type in (OAuthType.WITH_REFRESH, OAuthType.WITH_ROTATING_REFRESH):
                should_create_token_manager = True
                logger.debug(
                    f"✅ OAuth source {short_name} with oauth_type={source_model.oauth_type} "
                    f"will use token manager for refresh"
                )
            else:
                logger.debug(
                    f"⏭️ Skipping token manager for {short_name} - "
                    f"oauth_type={source_model.oauth_type} does not support token refresh"
                )

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
                    "config_fields": source_connection_data.get("config_fields"),
                },
            )()

            token_manager = TokenManager(
                db=db,
                source_short_name=short_name,
                source_connection=minimal_source_connection,
                ctx=ctx,
                initial_credentials=source_credentials,
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
    async def _create_destination_instances(  # noqa: C901
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        collection: schemas.Collection,
        ctx: ApiContext,
        logger: ContextualLogger,
    ) -> list[BaseDestination]:
        """Create destination instances with unified credentials pattern (matches sources).

        Handles two special cases:
        1. NATIVE_QDRANT_UUID: Uses settings, no credentials needed
        2. Org-specific destinations (e.g., S3): Loads credentials from Connection

        Args:
        -----
            db (AsyncSession): The database session
            sync (schemas.Sync): The sync object
            collection (schemas.Collection): The collection object
            ctx (ApiContext): The API context
            logger (ContextualLogger): The contextual logger with sync metadata

        Returns:
        --------
            list[BaseDestination]: A list of successfully created destination instances

        Raises:
        -------
            ValueError: If no destinations could be created
        """
        destinations = []

        # Create all destinations from destination_connection_ids
        for destination_connection_id in sync.destination_connection_ids:
            try:
                # Special case: Native Qdrant (uses settings, no DB connection)
                if destination_connection_id == NATIVE_QDRANT_UUID:
                    logger.info("Using native Qdrant destination (settings-based)")
                    destination_model = await crud.destination.get_by_short_name(db, "qdrant")
                    if not destination_model:
                        logger.warning("Qdrant destination model not found")
                        continue

                    destination_schema = schemas.Destination.model_validate(destination_model)
                    destination_class = resource_locator.get_destination(destination_schema)

                    # Fail-fast: vector_size must be set
                    if collection.vector_size is None:
                        raise ValueError(f"Collection {collection.id} has no vector_size set.")

                    # Native Qdrant: no credentials (uses settings)
                    destination = await destination_class.create(
                        credentials=None,
                        config=None,
                        collection_id=collection.id,
                        organization_id=collection.organization_id,
                        vector_size=collection.vector_size,
                        logger=logger,
                    )

                    destinations.append(destination)
                    logger.info("Created native Qdrant destination")
                    continue

                # Regular case: Load connection from database
                destination_connection = await crud.connection.get(
                    db, destination_connection_id, ctx
                )
                if not destination_connection:
                    logger.warning(
                        f"Destination connection {destination_connection_id} not found, skipping"
                    )
                    continue

                destination_model = await crud.destination.get_by_short_name(
                    db, destination_connection.short_name
                )
                if not destination_model:
                    logger.warning(
                        f"Destination {destination_connection.short_name} not found, skipping"
                    )
                    continue

                # Load credentials (contains both auth and config)
                destination_credentials = None
                if (
                    destination_model.auth_config_class
                    and destination_connection.integration_credential_id
                ):
                    credential = await crud.integration_credential.get(
                        db, destination_connection.integration_credential_id, ctx
                    )
                    if credential:
                        decrypted_credential = credentials.decrypt(credential.encrypted_credentials)
                        auth_config_class = resource_locator.get_auth_config(
                            destination_model.auth_config_class
                        )
                        destination_credentials = auth_config_class.model_validate(
                            decrypted_credential
                        )

                # Create destination instance with credentials (config=None)
                destination_schema = schemas.Destination.model_validate(destination_model)
                destination_class = resource_locator.get_destination(destination_schema)

                destination = await destination_class.create(
                    credentials=destination_credentials,
                    config=None,  # Everything is in credentials for now
                    collection_id=collection.id,
                    organization_id=collection.organization_id,
                    logger=logger,
                    collection_readable_id=collection.readable_id,
                    sync_id=sync.id,
                )

                destinations.append(destination)
                logger.info(
                    f"Created destination: {destination_connection.short_name} "
                    f"(connection_id={destination_connection_id})"
                )
            except Exception as e:
                # Log error but continue to next destination
                logger.error(
                    f"Failed to create destination {destination_connection_id}: {e}", exc_info=True
                )
                continue

        if not destinations:
            raise ValueError(
                "No valid destinations could be created for sync. "
                f"Tried {len(sync.destination_connection_ids)} connection(s)."
            )

        logger.info(
            f"Successfully created {len(destinations)} destination(s) "
            f"out of {len(sync.destination_connection_ids)} configured"
        )

        return destinations

    # NOTE: Transformers removed - chunking now happens in entity_pipeline.py

    @classmethod
    async def _get_entity_definition_map(cls, db: AsyncSession) -> dict[type[BaseEntity], UUID]:
        """Get entity definition map.

        Map entity class to entity definition id.

        Example key-value pair:
            <class 'airweave.platform.entities.trello.TrelloBoard'>: entity_definition_id
        """
        # Ensure the reserved polymorphic entity definition exists (idempotent).
        await init_db_with_entity_definitions(db)

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
