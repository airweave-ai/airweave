"""Search service for vector database integrations."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException
from airweave.platform.embedding_models.local_text2vec import LocalText2Vec
from airweave.platform.embedding_models.openai_text2vec import OpenAIText2Vec
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
            # e.g., neo4j + qdrant for GraphRAG.
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

            # Initialize destination class
            destination_class = resource_locator.get_destination(destination_model)

            # Use OpenAI embeddings if API key is available
            if settings.OPENAI_API_KEY:
                logger.info(f"Using OpenAI embedding model for search in sync {sync_id}")
                embedding_model = OpenAIText2Vec(api_key=settings.OPENAI_API_KEY)
            else:
                logger.info(f"Using local embedding model for search in sync {sync_id}")
                embedding_model = LocalText2Vec()

            vector = await embedding_model.embed(query)
            destination = await destination_class.create(sync_id=sync_id)

            # Perform search
            results = await destination.search(vector)

            return results

        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            raise


# Create singleton instance
search_service = SearchService()
