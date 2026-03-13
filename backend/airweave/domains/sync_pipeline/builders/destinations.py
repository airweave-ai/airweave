"""Destinations context builder for sync operations.

Handles destination creation and entity definition map loading.
Vespa is the sole destination; class is referenced directly.
"""

from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.core.constants.reserved_ids import NATIVE_VESPA_UUID
from airweave.core.context import BaseContext
from airweave.core.logging import ContextualLogger
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.destinations.vespa import VespaDestination
from airweave.platform.entities._base import BaseEntity
from airweave.domains.sync_pipeline.config import SyncConfig


class DestinationsContextBuilder:
    """Builds destinations context with all required configuration."""

    @classmethod
    async def build(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        collection: schemas.CollectionRecord,
        ctx: BaseContext,
        logger: ContextualLogger,
        execution_config: Optional[SyncConfig] = None,
    ) -> tuple:
        """Build destinations and entity map.

        Args:
            db: Database session
            sync: Sync configuration
            collection: Target collection
            ctx: Base context (provides org identity for CRUD)
            logger: Contextual logger
            execution_config: Optional execution config for filtering

        Returns:
            Tuple of (destinations, entity_map).
        """
        destinations = await cls._create_destinations(
            db=db,
            sync=sync,
            collection=collection,
            ctx=ctx,
            logger=logger,
            execution_config=execution_config,
        )
        entity_map = cls._get_entity_definition_map()

        return destinations, entity_map

    @classmethod
    async def build_for_collection(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        collection: schemas.CollectionRecord,
        ctx: BaseContext,
        logger: ContextualLogger,
    ) -> tuple:
        """Build destinations for collection-level operations.

        Simplified version without execution_config filtering.

        Args:
            db: Database session
            sync: Sync configuration
            collection: Target collection
            ctx: Base context
            logger: Contextual logger

        Returns:
            Tuple of (destinations, entity_map).
        """
        return await cls.build(
            db=db,
            sync=sync,
            collection=collection,
            ctx=ctx,
            logger=logger,
            execution_config=None,
        )

    @classmethod
    async def build_for_cleanup(
        cls,
        db: AsyncSession,
        collection: schemas.CollectionRecord,
        logger: ContextualLogger,
    ) -> List[BaseDestination]:
        """Build destinations for cleanup operations (no sync required).

        Args:
            db: Database session
            collection: Target collection
            logger: Logger for operations

        Returns:
            List of destination instances ready for deletion operations.
        """
        destinations = []
        try:
            dest = await cls._create_vespa(collection, logger)
            if dest:
                destinations.append(dest)
        except Exception as e:
            logger.warning(f"Failed to create Vespa destination: {e}")

        return destinations

    # -------------------------------------------------------------------------
    # Private: Destination Creation
    # -------------------------------------------------------------------------

    @classmethod
    async def _create_destinations(
        cls,
        db: AsyncSession,
        sync: schemas.Sync,
        collection: schemas.CollectionRecord,
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
        collection: schemas.CollectionRecord,
        ctx,
        logger: ContextualLogger,
    ) -> Optional[BaseDestination]:
        """Create a single destination instance."""
        if destination_connection_id != NATIVE_VESPA_UUID:
            logger.warning(f"Unknown destination connection {destination_connection_id}, skipping")
            return None
        return await cls._create_vespa(collection, logger)

    @classmethod
    async def _create_vespa(
        cls,
        collection: schemas.CollectionRecord,
        logger: ContextualLogger,
    ) -> BaseDestination:
        """Create native Vespa destination directly."""
        logger.info("Using native Vespa destination (settings-based)")
        destination = await VespaDestination.create(
            credentials=None,
            config=None,
            collection_id=collection.id,
            organization_id=collection.organization_id,
            vector_size=None,
            logger=logger,
        )
        logger.info("Created native Vespa destination")
        return destination

    # -------------------------------------------------------------------------
    # Private: Entity Definition Map
    # -------------------------------------------------------------------------

    @classmethod
    def _get_entity_definition_map(cls) -> Dict[type[BaseEntity], str]:
        """Get entity definition map (entity class -> entity_definition_short_name)."""
        # [code blue] todo: remove container import
        from airweave.core.container import container as app_container

        return {
            entry.entity_class_ref: entry.short_name
            for entry in app_container.entity_definition_registry.list_all()
        }

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
            targets = execution_config.destinations.target_destinations
            logger.info(f"Using target_destinations from config: {targets}")
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
