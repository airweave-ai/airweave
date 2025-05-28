"""Module for sync factory that creates context and orchestrator instances."""

import importlib
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core import credentials
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import LoggerConfigurator
from airweave.platform.auth.services import oauth2_service
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.embedding_models._base import BaseEmbeddingModel
from airweave.platform.embedding_models.local_text2vec import LocalText2Vec
from airweave.platform.embedding_models.openai_text2vec import OpenAIText2Vec
from airweave.platform.entities._base import BaseEntity
from airweave.platform.locator import resource_locator
from airweave.platform.sources._base import BaseSource
from airweave.platform.sync.context import SyncContext
from airweave.platform.sync.entity_processor import EntityProcessor
from airweave.platform.sync.orchestrator import SyncOrchestrator
from airweave.platform.sync.pubsub import SyncProgress
from airweave.platform.sync.router import SyncDAGRouter
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
        current_user: schemas.User,
        access_token: Optional[str] = None,
        max_workers: int = 20,
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
            current_user: The current user
            access_token: Optional token to use instead of stored credentials
            max_workers: Maximum number of concurrent workers (default: 20)

        Returns:
            A dedicated SyncOrchestrator instance
        """
        # Create sync context
        sync_context = await cls._create_sync_context(
            db=db,
            sync=sync,
            sync_job=sync_job,
            dag=dag,
            collection=collection,
            source_connection=source_connection,
            current_user=current_user,
            access_token=access_token,
        )

        # Create entity processor
        entity_processor = EntityProcessor()

        # Create worker pool
        worker_pool = AsyncWorkerPool(max_workers=max_workers)

        # Create dedicated orchestrator instance
        orchestrator = SyncOrchestrator(
            entity_processor=entity_processor,
            worker_pool=worker_pool,
            sync_context=sync_context,
        )

        # Initialize entity tracking
        entity_processor.initialize_tracking(sync_context)

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
        current_user: schemas.User,
        access_token: Optional[str] = None,
    ) -> SyncContext:
        """Create a sync context.

        Args:
            db: Database session
            sync: The sync configuration
            sync_job: The sync job
            dag: The DAG for the sync
            collection: The collection to sync to
            source_connection: The source connection
            current_user: The current user
            access_token: Optional token to use instead of stored credentials

        Returns:
            SyncContext object with all required components
        """
        # Fetch white label if set in sync
        white_label = None
        if source_connection.white_label_id:
            white_label = await crud.white_label.get(
                db, id=source_connection.white_label_id, current_user=current_user
            )

        source = await cls._create_source_instance(
            db=db,
            sync=sync,
            current_user=current_user,
            white_label=white_label,
            access_token=access_token,
        )
        embedding_model = cls._get_embedding_model(sync=sync)
        destinations = await cls._create_destination_instances(
            db=db,
            sync=sync,
            collection=collection,
            current_user=current_user,
        )
        transformers = await cls._get_transformer_callables(db=db, sync=sync)
        entity_map = await cls._get_entity_definition_map(db=db)

        progress = SyncProgress(sync_job.id)
        router = SyncDAGRouter(dag, entity_map)

        # Create a contextualized logger with sync job metadata
        logger = LoggerConfigurator.configure_logger(
            "airweave.platform.sync",
            dimensions={
                "sync_id": str(sync.id),
                "sync_job_id": str(sync_job.id),
                "user_id": str(current_user.id),
                # "org_id": str(sync.organization_id), TODO: add org id when we have orgs
            },
        )

        return SyncContext(
            source=source,
            destinations=destinations,
            embedding_model=embedding_model,
            transformers=transformers,
            sync=sync,
            sync_job=sync_job,
            dag=dag,
            collection=collection,
            source_connection=source_connection,
            progress=progress,
            router=router,
            entity_map=entity_map,
            current_user=current_user,
            logger=logger,
            white_label=white_label,
        )

    @classmethod
    async def _create_source_instance(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        current_user: schemas.User,
        white_label: Optional[schemas.WhiteLabel] = None,
        access_token: Optional[str] = None,
    ) -> BaseSource:
        """Create and configure the source instance based on authentication type."""
        # Retrieve source connection and model
        source_connection = await crud.connection.get(db, sync.source_connection_id, current_user)
        if not source_connection:
            raise NotFoundException("Source connection not found")

        # Get the source_connection record to access config_fields using sync_id
        source_connection_obj = await crud.source_connection.get_by_sync_id(
            db, sync_id=sync.id, current_user=current_user
        )
        if not source_connection_obj:
            raise NotFoundException("Source connection record not found")

        # Get config fields (will be empty dict if none)
        config_fields = source_connection_obj.config_fields or {}

        source_model = await crud.source.get_by_short_name(db, source_connection.short_name)
        if not source_model:
            raise NotFoundException(f"Source not found: {source_connection.short_name}")

        source_class = resource_locator.get_source(source_model)

        # If access token is provided, use it directly
        if access_token:
            return await source_class.create(access_token, config=config_fields)

        # Otherwise get credentials from database as before
        if not source_connection.integration_credential_id:
            raise NotFoundException("Source connection has no integration credential")

        credential = await cls._get_integration_credential(db, source_connection, current_user)
        decrypted_credential = credentials.decrypt(credential.encrypted_credentials)

        # If the source model requires auth configuration, validate it
        if source_model.auth_config_class:
            auth_config = resource_locator.get_auth_config(source_model.auth_config_class)
            source_credentials = auth_config.model_validate(decrypted_credential)

            # if the source_credential has a refresh token, exchange it for an access token
            if hasattr(source_credentials, "refresh_token") and source_credentials.refresh_token:
                oauth2_response = await oauth2_service.refresh_access_token(
                    db,
                    source_model.short_name,
                    current_user,
                    source_connection.id,
                    decrypted_credential,
                    white_label,
                )
                # Just use the access token
                source_credentials = oauth2_response.access_token
        else:
            source_credentials = decrypted_credential

        # Pass both credentials and config to source creation
        return await source_class.create(source_credentials, config=config_fields)

    @classmethod
    async def _get_integration_credential(
        cls,
        db: AsyncSession,
        source_connection: schemas.Connection,
        current_user: schemas.User,
    ) -> schemas.IntegrationCredential:
        """Get integration credential."""
        credential = await crud.integration_credential.get(
            db, source_connection.integration_credential_id, current_user
        )
        if not credential:
            raise NotFoundException("Source integration credential not found")
        return credential

    @classmethod
    def _get_embedding_model(cls, sync: schemas.Sync) -> BaseEmbeddingModel:
        """Get embedding model instance.

        If OpenAI API key is available, it will use OpenAI embeddings instead of local.

        Args:
            sync (schemas.Sync): The sync configuration

        Returns:
            BaseEmbeddingModel: The embedding model to use
        """
        # Use OpenAI if API key is available
        from airweave.core.logging import logger

        if settings.OPENAI_API_KEY:
            logger.info(f"Using OpenAI embedding model (text-embedding-3-small) for sync {sync.id}")
            return OpenAIText2Vec(api_key=settings.OPENAI_API_KEY)

        # Otherwise use the local model
        logger.info(f"Using local embedding model (MiniLM-L6-v2) for sync {sync.id}")
        return LocalText2Vec()

    @classmethod
    async def _create_destination_instances(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        collection: schemas.Collection,
        current_user: schemas.User,
    ) -> list[BaseDestination]:
        """Create destination instances.

        Args:
        -----
            db (AsyncSession): The database session
            sync (schemas.Sync): The sync object
            collection (schemas.Collection): The collection object
            current_user (schemas.User): The current user

        Returns:
        --------
            list[BaseDestination]: A list of destination instances
        """
        destination_connection_id = sync.destination_connection_ids[0]

        destination_connection = await crud.connection.get(
            db, destination_connection_id, current_user
        )
        if not destination_connection:
            raise NotFoundException(
                (
                    f"Destination connection not found for user {current_user.email}"
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
        destination = await destination_class.create(collection_id=collection.id)

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
            full_module_name = f"airweave.platform.entities.{entity_definition.module_name}"
            module = importlib.import_module(full_module_name)
            entity_class = getattr(module, entity_definition.class_name)
            entity_definition_map[entity_class] = entity_definition.id

        return entity_definition_map
