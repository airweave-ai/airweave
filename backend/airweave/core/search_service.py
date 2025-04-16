"""Search service for vector database integrations."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.exceptions import NotFoundException
from airweave.platform.embedding_models.local_text2vec import LocalText2Vec
from airweave.platform.locator import resource_locator

logger = logging.getLogger(__name__)


class SearchService:
    """Service for handling vector database searches."""

    async def search(
        self,
        db: AsyncSession,
        query: str,
        sync_id: UUID,
        current_user: schemas.User,
    ) -> list[dict]:
        """Search across vector database using existing connections.

        Args:
            db (AsyncSession): Database session
            query (str): Search query text
            sync_id (UUID): ID of the sync to search within
            current_user (schemas.User): Current user performing the search

        Returns:
            list[dict]: List of search results

        Raises:
            NotFoundException: If sync or connections not found
        """
        try:
            # Get sync configuration
            sync = await crud.sync.get(db, id=sync_id, current_user=current_user)
            if not sync:
                raise NotFoundException("Sync not found")

            # Check if there are destination connections
            if not sync.destination_connection_ids or len(sync.destination_connection_ids) == 0:
                raise NotFoundException("No destination connections found for this sync")

            # TODO: In the future, implement multi-destination search capability,
            # e.g., neo4j + weaviate for GraphRAG.
            # Currently, we only use the first destination for searching, but eventually
            # we should support searching across all destinations and aggregating results
            destination_connection_id = sync.destination_connection_ids[0]

            # Get the destination connection
            connection = await crud.connection.get(db, destination_connection_id, current_user)
            if not connection:
                raise NotFoundException("Destination connection not found")

            # Get the destination model
            destination_model = await crud.destination.get_by_short_name(db, connection.short_name)
            if not destination_model:
                raise NotFoundException("Destination not found")

            # Check if this is a native connection
            is_native = crud.connection._is_native_connection(connection)

            # Get credentials if not a native connection
            if not is_native:
                if connection.integration_credential_id:
                    integration_credential = await crud.integration_credential.get(
                        db,
                        connection.integration_credential_id,
                        current_user,
                    )
                    if not integration_credential:
                        raise NotFoundException("Destination credentials not found")
                else:
                    logger.warning(
                        f"Non-native connection {connection.id} does not have "
                        f"integration credentials, but will attempt to continue with search."
                    )

            # Get source model for permission filtering
            source_model = await crud.source.get_by_id(db, sync.source_id)
            if not source_model:
                raise NotFoundException("Source not found")

            # Initialize destination class
            destination_class = resource_locator.get_destination(destination_model)

            # TODO: Add a step to get the embedding model from the sync
            embedding_model = LocalText2Vec()

            vector = await embedding_model.embed(query)
            destination = await destination_class.create(sync_id=sync_id)

            # Apply source-specific permission filters
            permission_filters = None
            source_type = source_model.short_name

            if source_type == "asana":
                # Apply Asana-specific permission filters
                from airweave.platform.permissions.asana import AsanaPermissionFilters

                logger.info(f"Applying Asana permission filters for user {current_user.email}")
                try:
                    permission_filters = await AsanaPermissionFilters.build_filters(
                        user_email=current_user.email
                    )
                except Exception as e:
                    logger.error(f"Error applying Asana permission filters: {e}")
                    # Continue without permission filters in case of error

            # Add other source types as they are implemented
            # elif source_type == "google_drive":
            #     from airweave.platform.permissions.filters import GoogleDrivePermissionFilters
            #     permission_filters = await GoogleDrivePermissionFilters.build_filters(...)

            # Log if we're applying permission filters
            if permission_filters:
                logger.info(f"Applied permission filters for {source_type}")
            else:
                logger.info(f"No permission filters applied for {source_type}")

            # Perform search with optional permission filters
            results = await destination.search(vector, permission_filters=permission_filters)

            return results

        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            raise


# Create singleton instance
search_service = SearchService()
