"""Destinations context builder for sync operations.

Handles destination creation with:
- Native destinations (Vespa) using settings
- Custom destinations with credentials
- Entity definition map loading
"""

import asyncio
import importlib
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core import credentials
from airweave.core.constants.reserved_ids import (
    NATIVE_VESPA_UUID,
    RESERVED_TABLE_ENTITY_ID,
)
from airweave.core.logging import ContextualLogger
from airweave.db.init_db_native import init_db_with_entity_definitions
from airweave.platform.contexts.destinations import DestinationsContext
from airweave.platform.contexts.infra import InfraContext
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.entities._base import BaseEntity
from airweave.platform.locator import resource_locator
from airweave.platform.sync.config import SyncConfig


class DestinationsContextBuilder:
    """Builds destinations context with all required configuration."""

    @classmethod
    async def build(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        collection: schemas.Collection,
        infra: InfraContext,
        execution_config: Optional[SyncConfig] = None,
    ) -> DestinationsContext:
        """Build complete destinations context.

        Args:
            db: Database session
            sync: Sync configuration
            collection: Target collection
            infra: Infrastructure context (provides ctx and logger)
            execution_config: Optional execution config for filtering

        Returns:
            DestinationsContext with configured destinations and entity map.
        """
        ctx = infra.ctx
        logger = infra.logger

        # Build in parallel: destinations and entity map
        destinations, entity_map = await asyncio.gather(
            cls._create_destinations(
                db=db,
                sync=sync,
                collection=collection,
                ctx=ctx,
                logger=logger,
                execution_config=execution_config,
            ),
            cls._get_entity_definition_map(db=db),
        )

        return DestinationsContext(
            destinations=destinations,
            entity_map=entity_map,
        )

    @classmethod
    async def build_for_collection(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        collection: schemas.Collection,
        infra: InfraContext,
    ) -> DestinationsContext:
        """Build destinations context for collection-level operations.

        Simplified version without execution_config filtering.

        Args:
            db: Database session
            sync: Sync configuration
            collection: Target collection
            infra: Infrastructure context

        Returns:
            DestinationsContext with all configured destinations.
        """
        return await cls.build(
            db=db,
            sync=sync,
            collection=collection,
            infra=infra,
            execution_config=None,
        )

    @classmethod
    async def build_for_cleanup(
        cls,
        db: AsyncSession,
        collection: schemas.Collection,
        logger: ContextualLogger,
    ) -> List[BaseDestination]:
        """Build destinations for cleanup operations (no sync required).

        Creates native destinations for deletion operations.
        Uses the same UUID constants as sync to ensure consistency.

        Args:
            db: Database session
            collection: Target collection
            logger: Logger for operations

        Returns:
            List of destination instances ready for deletion operations.
        """
        # Map native UUIDs to their creator methods
        native_creators = {
            NATIVE_VESPA_UUID: cls._create_native_vespa,
        }

        destinations = []
        for dest_uuid, creator in native_creators.items():
            try:
                dest = await creator(db, collection, logger)
                if dest:
                    destinations.append(dest)
            except Exception as e:
                logger.warning(f"Failed to create destination {dest_uuid}: {e}")

        return destinations

    # -------------------------------------------------------------------------
    # Private: Destination Creation
    # -------------------------------------------------------------------------

    @classmethod
    async def _create_destinations(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        collection: schemas.Collection,
        ctx,
        logger: ContextualLogger,
        execution_config: Optional[SyncConfig] = None,
    ) -> List[BaseDestination]:
        """Create destination instances."""
        destinations = []

        # Filter destination IDs based on execution_config
        destination_ids = cls._filter_destination_ids(
            sync.destination_connection_ids, execution_config, logger
        )

        for destination_connection_id in destination_ids:
            try:
                destination = await cls._create_single_destination(
                    db=db,
                    destination_connection_id=destination_connection_id,
                    sync=sync,
                    collection=collection,
                    ctx=ctx,
                    logger=logger,
                )
                if destination:
                    destinations.append(destination)
            except Exception as e:
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

    @classmethod
    async def _create_single_destination(
        cls,
        db: AsyncSession,
        destination_connection_id: UUID,
        sync: schemas.Sync,
        collection: schemas.Collection,
        ctx,
        logger: ContextualLogger,
    ) -> Optional[BaseDestination]:
        """Create a single destination instance."""
        # Special case: Native Vespa
        if destination_connection_id == NATIVE_VESPA_UUID:
            return await cls._create_native_vespa(db, collection, logger)

        # Regular case: Load from database
        return await cls._create_custom_destination(
            db=db,
            destination_connection_id=destination_connection_id,
            sync=sync,
            collection=collection,
            ctx=ctx,
            logger=logger,
        )

    @classmethod
    async def _create_native_vespa(
        cls,
        db: AsyncSession,
        collection: schemas.Collection,
        logger: ContextualLogger,
    ) -> Optional[BaseDestination]:
        """Create native Vespa destination."""
        logger.info("Using native Vespa destination (settings-based)")
        destination_model = await crud.destination.get_by_short_name(db, "vespa")
        if not destination_model:
            logger.warning("Vespa destination model not found")
            return None

        destination_schema = schemas.Destination.model_validate(destination_model)
        destination_class = resource_locator.get_destination(destination_schema)

        destination = await destination_class.create(
            credentials=None,
            config=None,
            collection_id=collection.id,
            organization_id=collection.organization_id,
            vector_size=None,  # Vespa handles embeddings internally
            logger=logger,
        )

        logger.info("Created native Vespa destination")
        return destination

    @classmethod
    async def _create_custom_destination(
        cls,
        db: AsyncSession,
        destination_connection_id: UUID,
        sync: schemas.Sync,
        collection: schemas.Collection,
        ctx,
        logger: ContextualLogger,
    ) -> Optional[BaseDestination]:
        """Create custom destination from database connection."""
        destination_connection = await crud.connection.get(db, destination_connection_id, ctx)
        if not destination_connection:
            logger.warning(
                f"Destination connection {destination_connection_id} not found, skipping"
            )
            return None

        destination_model = await crud.destination.get_by_short_name(
            db, destination_connection.short_name
        )
        if not destination_model:
            logger.warning(f"Destination {destination_connection.short_name} not found, skipping")
            return None

        # Load credentials
        destination_credentials = None
        if destination_model.auth_config_class and destination_connection.integration_credential_id:
            credential = await crud.integration_credential.get(
                db, destination_connection.integration_credential_id, ctx
            )
            if credential:
                decrypted_credential = credentials.decrypt(credential.encrypted_credentials)
                auth_config_class = resource_locator.get_auth_config(
                    destination_model.auth_config_class
                )
                destination_credentials = auth_config_class.model_validate(decrypted_credential)

        # Create destination instance
        destination_schema = schemas.Destination.model_validate(destination_model)
        destination_class = resource_locator.get_destination(destination_schema)

        destination = await destination_class.create(
            credentials=destination_credentials,
            config=None,
            collection_id=collection.id,
            organization_id=collection.organization_id,
            logger=logger,
            collection_readable_id=collection.readable_id,
            sync_id=sync.id,
        )

        logger.info(
            f"Created destination: {destination_connection.short_name} "
            f"(connection_id={destination_connection_id})"
        )
        return destination

    # -------------------------------------------------------------------------
    # Private: Entity Definition Map
    # -------------------------------------------------------------------------

    @classmethod
    async def _get_entity_definition_map(cls, db: AsyncSession) -> Dict[type[BaseEntity], UUID]:
        """Get entity definition map (entity class -> entity_definition_id)."""
        # Ensure the reserved polymorphic entity definition exists (idempotent)
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

    # -------------------------------------------------------------------------
    # Private: Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _filter_destination_ids(
        destination_ids: List[UUID],
        execution_config: Optional[SyncConfig],
        logger: ContextualLogger,
    ) -> List[UUID]:
        """Filter destination IDs based on execution config.

        Priority order:
        1. target_destinations (explicit whitelist) - highest priority
        2. exclude_destinations + skip_vespa (combined exclusions)
        """
        if not execution_config:
            return destination_ids

        # Priority 1: target_destinations (explicit whitelist overrides everything)
        if execution_config.destinations.target_destinations:
            logger.info(
                f"Using target_destinations from config: {execution_config.destinations.target_destinations}"
            )
            return execution_config.destinations.target_destinations

        # Priority 2: Build combined exclusion set from all exclusion flags
        exclusions: set[UUID] = set()

        # Add explicit UUID exclusions
        if execution_config.destinations.exclude_destinations:
            exclusions.update(execution_config.destinations.exclude_destinations)

        # Add native vector DB exclusions from boolean flags
        if execution_config.destinations.skip_vespa:
            exclusions.add(NATIVE_VESPA_UUID)
            logger.info("Excluding native Vespa (skip_vespa=True)")

        # Apply exclusions
        if exclusions:
            original_count = len(destination_ids)
            filtered_ids = [dest_id for dest_id in destination_ids if dest_id not in exclusions]
            excluded_count = original_count - len(filtered_ids)
            if excluded_count > 0:
                logger.info(f"Excluded {excluded_count} destination(s) via execution_config")
            return filtered_ids

        return destination_ids
