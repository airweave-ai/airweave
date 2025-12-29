"""Destination builder - creates and configures destination instances.

This is an internal implementation detail of the factory module.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core import credentials
from airweave.core.constants.reserved_ids import NATIVE_QDRANT_UUID
from airweave.core.logging import ContextualLogger
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.locator import resource_locator


class DestinationBuilder:
    """Builder for creating destination instances.

    Handles:
    - Loading destination connections
    - Credential decryption
    - Native Qdrant (settings-based) vs custom destinations
    - Filtering by role (active/shadow/deprecated)
    """

    def __init__(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        logger: ContextualLogger,
    ):
        """Initialize the destination builder."""
        self.db = db
        self.ctx = ctx
        self.logger = logger

    async def build(
        self,
        sync: schemas.Sync,
        collection: schemas.Collection,
    ) -> list[BaseDestination]:
        """Build destination instances for a sync.

        Respects destination roles:
        - ACTIVE: receives writes + serves queries
        - SHADOW: receives writes only (migration testing)
        - DEPRECATED: skipped (no writes)
        """
        destination_ids = await self._get_active_ids(sync)

        destinations = await self.build_for_ids(
            destination_ids=destination_ids,
            collection=collection,
            sync_id=sync.id,
        )

        if not destinations:
            raise ValueError(
                f"No valid destinations could be created for sync. "
                f"Tried {len(sync.destination_connection_ids)} connection(s)."
            )

        self.logger.info(
            f"Successfully created {len(destinations)} destination(s) "
            f"out of {len(sync.destination_connection_ids)} configured"
        )

        return destinations

    async def build_for_ids(
        self,
        destination_ids: list[UUID],
        collection: schemas.Collection,
        sync_id: Optional[UUID] = None,
    ) -> list[BaseDestination]:
        """Build destination instances for specific connection IDs."""
        destinations = []

        for dest_id in destination_ids:
            try:
                destination = await self._create_single(
                    dest_id=dest_id,
                    collection=collection,
                    sync_id=sync_id,
                )
                if destination:
                    destinations.append(destination)
            except Exception as e:
                self.logger.error(
                    f"Failed to create destination {dest_id}: {e}",
                    exc_info=True,
                )

        return destinations

    async def _get_active_ids(self, sync: schemas.Sync) -> list[UUID]:
        """Get destination IDs that should receive writes."""
        slots = await crud.sync_connection.get_active_and_shadow(self.db, sync_id=sync.id)

        if slots:
            destination_ids = [slot.connection_id for slot in slots]
            deprecated_count = len(sync.destination_connection_ids) - len(destination_ids)
            if deprecated_count > 0:
                self.logger.info(
                    f"Filtered {deprecated_count} deprecated destination(s), "
                    f"using {len(destination_ids)} active/shadow destination(s)"
                )
            return destination_ids

        return list(sync.destination_connection_ids)

    async def _create_single(
        self,
        dest_id: UUID,
        collection: schemas.Collection,
        sync_id: Optional[UUID],
    ) -> Optional[BaseDestination]:
        """Create a single destination instance."""
        if dest_id == NATIVE_QDRANT_UUID:
            return await self._create_native_qdrant(collection)

        return await self._create_custom_destination(
            dest_id=dest_id,
            collection=collection,
            sync_id=sync_id,
        )

    async def _create_native_qdrant(
        self,
        collection: schemas.Collection,
    ) -> Optional[BaseDestination]:
        """Create native Qdrant destination (settings-based, no credentials)."""
        self.logger.info("Using native Qdrant destination (settings-based)")

        destination_model = await crud.destination.get_by_short_name(self.db, "qdrant")
        if not destination_model:
            self.logger.warning("Qdrant destination model not found")
            return None

        if collection.vector_size is None:
            raise ValueError(f"Collection {collection.id} has no vector_size set.")

        dest_schema = schemas.Destination.model_validate(destination_model)
        dest_class = resource_locator.get_destination(dest_schema)

        destination = await dest_class.create(
            credentials=None,
            config=None,
            collection_id=collection.id,
            organization_id=collection.organization_id,
            vector_size=collection.vector_size,
            logger=self.logger,
        )

        self.logger.info("Created native Qdrant destination")
        return destination

    async def _create_custom_destination(
        self,
        dest_id: UUID,
        collection: schemas.Collection,
        sync_id: Optional[UUID],
    ) -> Optional[BaseDestination]:
        """Create a custom destination with credentials."""
        connection = await crud.connection.get(self.db, dest_id, self.ctx)
        if not connection:
            self.logger.warning(f"Destination connection {dest_id} not found, skipping")
            return None

        destination_model = await crud.destination.get_by_short_name(self.db, connection.short_name)
        if not destination_model:
            self.logger.warning(f"Destination {connection.short_name} not found, skipping")
            return None

        dest_credentials = None
        if destination_model.auth_config_class and connection.integration_credential_id:
            credential = await crud.integration_credential.get(
                self.db, connection.integration_credential_id, self.ctx
            )
            if credential:
                decrypted = credentials.decrypt(credential.encrypted_credentials)
                auth_config = resource_locator.get_auth_config(destination_model.auth_config_class)
                dest_credentials = auth_config.model_validate(decrypted)

        dest_schema = schemas.Destination.model_validate(destination_model)
        dest_class = resource_locator.get_destination(dest_schema)

        destination = await dest_class.create(
            credentials=dest_credentials,
            config=None,
            collection_id=collection.id,
            organization_id=collection.organization_id,
            logger=self.logger,
            collection_readable_id=collection.readable_id,
            sync_id=sync_id,
        )

        self.logger.info(f"Created destination: {connection.short_name} (connection_id={dest_id})")
        return destination
