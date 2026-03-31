"""Destinations context builder for sync operations.

Vespa is the sole destination; class is referenced directly.
"""

from typing import List, Optional
from uuid import UUID

from airweave import schemas
from airweave.core.constants.reserved_ids import NATIVE_VESPA_UUID
from airweave.core.logging import ContextualLogger
from airweave.domains.sync_pipeline.config import SyncConfig
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.destinations.vespa import VespaDestination


class DestinationsContextBuilder:
    """Builds destinations context with all required configuration."""

    @classmethod
    async def build_destinations(
        cls,
        sync: schemas.Sync,
        collection: schemas.CollectionRecord,
        logger: ContextualLogger,
        execution_config: Optional[SyncConfig] = None,
        source_supports_acl: bool = False,
    ) -> List[BaseDestination]:
        """Build destinations."""
        return await cls._create_destinations(
            sync=sync,
            collection=collection,
            logger=logger,
            execution_config=execution_config,
            source_supports_acl=source_supports_acl,
        )

    # -------------------------------------------------------------------------
    # Private: Destination Creation
    # -------------------------------------------------------------------------

    @classmethod
    async def _create_destinations(
        cls,
        sync: schemas.Sync,
        collection: schemas.CollectionRecord,
        logger: ContextualLogger,
        execution_config: Optional[SyncConfig] = None,
        source_supports_acl: bool = False,
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
                    destination_connection_id=destination_connection_id,
                    collection=collection,
                    logger=logger,
                    source_supports_acl=source_supports_acl,
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
        destination_connection_id: UUID,
        collection: schemas.CollectionRecord,
        logger: ContextualLogger,
        source_supports_acl: bool = False,
    ) -> Optional[BaseDestination]:
        """Create a single destination instance."""
        if destination_connection_id != NATIVE_VESPA_UUID:
            logger.warning(f"Unknown destination connection {destination_connection_id}, skipping")
            return None
        return await cls._create_vespa(collection, logger, source_supports_acl=source_supports_acl)

    @classmethod
    async def _create_vespa(
        cls,
        collection: schemas.CollectionRecord,
        logger: ContextualLogger,
        source_supports_acl: bool = False,
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
            source_supports_acl=source_supports_acl,
        )
        logger.info("Created native Vespa destination")
        return destination

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
