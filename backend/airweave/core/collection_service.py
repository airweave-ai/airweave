"""Collection service."""

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.core.exceptions import NotFoundException
from airweave.core.logging import ContextualLogger
from airweave.db.unit_of_work import UnitOfWork
from airweave.platform.destinations.qdrant import QdrantDestination
from airweave.platform.embedding_models._base import BaseEmbeddingModel
from airweave.platform.embedding_models.local_text2vec import LocalText2Vec
from airweave.platform.embedding_models.openai_text2vec import OpenAIText2Vec


def _determine_vector_size() -> int:
    """Determine the vector size for a collection based on the source connection."""
    if settings.OPENAI_API_KEY:
        return 1536
    else:
        return 384


def get_embedding_model_for_collection(
    collection: schemas.Collection, logger: ContextualLogger
) -> BaseEmbeddingModel:
    """Get the embedding model for a collection based on its vector size.
    
    Args:
        collection: The collection object with vector_size field
        logger: Logger instance
        
    Returns:
        BaseEmbeddingModel: The embedding model
        
    Raises:
        ValueError: If vector_size is not supported or if required API key is missing
    """
    vector_size = collection.vector_size
    
    if vector_size is None:
        logger.warning(
            f"Collection {collection.readable_id} has no vector_size set, "
            f"falling back to runtime detection"
        )
        if settings.OPENAI_API_KEY:
            return OpenAIText2Vec(api_key=settings.OPENAI_API_KEY, logger=logger)
        else:
            return LocalText2Vec(logger=logger)
    
    # Select embedding model based on stored vector size
    if vector_size == 384:
        logger.info(
            f"Using local embedding model (384D) for collection {collection.readable_id}"
        )
        return LocalText2Vec(logger=logger)
    elif vector_size == 1536:
        if not settings.OPENAI_API_KEY:
            raise ValueError(
                f"Collection '{collection.readable_id}' requires OpenAI embeddings (1536D) "
                f"but OPENAI_API_KEY is not set. "
                f"Please either:\n"
                f"1. Set OPENAI_API_KEY environment variable, or\n"
                f"2. Create a new collection (which will use local 384D embeddings), or\n"
            )
        logger.info(
            f"Using OpenAI embedding model (1536D) for collection {collection.readable_id}"
        )
        return OpenAIText2Vec(api_key=settings.OPENAI_API_KEY, logger=logger)
    else:
        raise ValueError(
            f"Unsupported vector size {vector_size} for collection {collection.readable_id}. "
            f"Supported sizes: 384 (local), 1536 (OpenAI)"
        )


class CollectionService:
    """Service for managing collections.

    Manages the lifecycle of collections across the SQL datamodel and Qdrant.
    """

    async def create(
        self,
        db: AsyncSession,
        collection_in: schemas.CollectionCreate,
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> schemas.Collection:
        """Create a new collection."""
        if uow is None:
            # Unit of work is not provided, so we create a new one
            async with UnitOfWork(db) as uow:
                collection = await self._create(db, collection_in=collection_in, ctx=ctx, uow=uow)
        else:
            # Unit of work is provided, so we just create the collection
            collection = await self._create(db, collection_in=collection_in, ctx=ctx, uow=uow)

        return collection

    async def _create(
        self,
        db: AsyncSession,
        collection_in: schemas.CollectionCreate,
        ctx: ApiContext,
        uow: UnitOfWork,
    ) -> schemas.Collection:
        """Create a new collection."""
        # Check if the collection already exists
        try:
            existing_collection = await crud.collection.get_by_readable_id(
                db, readable_id=collection_in.readable_id, ctx=ctx
            )
        except NotFoundException:
            existing_collection = None

        if existing_collection:
            raise HTTPException(
                status_code=400, detail="Collection with this readable_id already exists"
            )

        # Determine vector size for this collection if not provided
        if collection_in.vector_size is None:
            collection_in.vector_size = _determine_vector_size()

        collection = await crud.collection.create(db, obj_in=collection_in, ctx=ctx, uow=uow)
        await uow.session.flush()

        # Create a Qdrant destination
        qdrant_destination = await QdrantDestination.create(
            collection_id=collection.id, logger=ctx.logger
        )

        await qdrant_destination.setup_collection(vector_size=collection_in.vector_size)

        return schemas.Collection.model_validate(collection, from_attributes=True)


# Singleton instance
collection_service = CollectionService()
