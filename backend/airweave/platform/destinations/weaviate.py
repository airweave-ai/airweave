"""Weaviate destination implementation."""

from uuid import UUID

import weaviate
from weaviate.classes.query import Filter
from weaviate.collections import Collection
from weaviate.collections.classes.config import DataType, Property

from airweave.platform.auth.schemas import AuthType
from airweave.platform.configs.auth import WeaviateAuthConfig
from airweave.platform.decorators import destination
from airweave.platform.destinations._base import VectorDBDestination
from airweave.platform.embedding_models._adapters import WeaviateModelAdapter
from airweave.platform.embedding_models._base import BaseEmbeddingModel
from airweave.platform.entities._base import ChunkEntity
from airweave.vector_db.weaviate_service import WeaviateService


@destination("Weaviate", "weaviate", AuthType.config_class, "WeaviateAuthConfig", labels=["Vector"])
class WeaviateDestination(VectorDBDestination):
    """Weaviate destination implementation."""

    def __init__(self):
        """Initialize Weaviate destination."""
        self.collection: Collection | None = None
        self.sync_id: UUID | None = None
        self.embedding_model: BaseEmbeddingModel | None = None
        self.collection_name: str | None = None
        self.cluster_url: str | None = None
        self.api_key: str | None = None

    @classmethod
    async def create(
        cls,
        sync_id: UUID,
        embedding_model: BaseEmbeddingModel,
    ) -> "WeaviateDestination":
        """Create a new Weaviate destination.

        Args:
            sync_id (UUID): The ID of the sync.
            embedding_model (BaseEmbeddingModel): The embedding model to use.

        Returns:
            WeaviateDestination: The created destination.
        """
        instance = cls()
        instance.sync_id = sync_id
        instance.collection_name = f"Entities_{instance._sanitize_collection_name(sync_id)}"
        instance.embedding_model = embedding_model

        # Get credentials for sync_id
        credentials = await cls.get_credentials()
        if credentials:
            instance.cluster_url = credentials.cluster_url
            instance.api_key = credentials.api_key
        else:
            instance.cluster_url = None
            instance.api_key = None

        # Set up initial collection
        await instance.setup_collection(sync_id)
        return instance

    @classmethod
    async def get_credentials(cls) -> WeaviateAuthConfig | None:
        """Get credentials for the destination from the user.

        Args:
            user (schemas.User): The user to get credentials for.

        Returns:
            WeaviateAuthConfig | None: The credentials for the destination.
        """
        # TODO: Implement this
        return None

    async def setup_collection(self, sync_id: UUID) -> None:
        """Set up the Weaviate collection for storing entities.

        Args:
            sync_id (UUID): The ID of the sync.
        """
        if not self.embedding_model:
            raise ValueError("Embedding model not configured")

        properties = [
            Property(name="source_name", data_type=DataType.TEXT),
            Property(name="entity_id", data_type=DataType.TEXT),
            Property(name="sync_id", data_type=DataType.UUID),
            Property(name="sync_job_id", data_type=DataType.UUID),
            Property(name="content", data_type=DataType.TEXT),
            Property(name="url", data_type=DataType.TEXT),
            Property(name="sync_metadata", data_type=DataType.TEXT),
            Property(
                name="breadcrumbs",
                data_type=DataType.OBJECT_ARRAY,
                nested_properties=[
                    Property(name="entity_id", data_type=DataType.TEXT),
                    Property(name="name", data_type=DataType.TEXT),
                    Property(name="type", data_type=DataType.TEXT),
                ],
            ),
            Property(name="white_label_user_identifier", data_type=DataType.TEXT),
            Property(name="white_label_id", data_type=DataType.UUID),
            Property(name="white_label_name", data_type=DataType.TEXT),
            Property(
                name="properties",
                data_type=DataType.OBJECT,
                nested_properties=[
                    Property(name="name", data_type=DataType.TEXT),
                    Property(name="value", data_type=DataType.TEXT),
                ],
            ),
        ]

        async with WeaviateService(
            weaviate_cluster_url=self.cluster_url,
            weaviate_api_key=self.api_key,
            embedding_model=self.embedding_model,
        ) as service:
            try:
                self.collection = await service.create_weaviate_collection(
                    collection_name=self.collection_name,
                    properties=properties,
                    vectorizer_config=WeaviateModelAdapter.get_vectorizer_config(
                        self.embedding_model
                    ),
                    generative_config=WeaviateModelAdapter.get_generative_config(
                        self.embedding_model
                    ),
                )
            except Exception as e:
                if "already exists" not in str(e):
                    raise
                self.collection = await service.get_weaviate_collection(self.collection_name)

    async def insert(self, entity: ChunkEntity) -> None:
        """Insert a single entity into Weaviate."""
        # Use the entity's to_storage_dict method to get properly serialized data
        data_object = entity.to_storage_dict()

        # Insert into Weaviate
        async with WeaviateService(
            weaviate_cluster_url=self.cluster_url,
            weaviate_api_key=self.api_key,
            embedding_model=self.embedding_model,
        ) as service:
            collection = await service.get_weaviate_collection(self.collection_name)
            await collection.data.insert(data_object, uuid=entity.db_entity_id)

    async def bulk_insert(self, entities: list[ChunkEntity]) -> None:
        """Bulk insert entities into Weaviate."""
        if not entities or not self.embedding_model:
            return

        async with WeaviateService(
            weaviate_cluster_url=self.cluster_url,
            weaviate_api_key=self.api_key,
            embedding_model=self.embedding_model,
        ) as service:
            collection = await service.get_weaviate_collection(self.collection_name)

            # Transform entities into the format Weaviate expects for uuid and properties
            objects_to_insert = []
            for entity in entities:
                # Use the entity's to_storage_dict method to get properly serialized data
                entity_data = entity.to_storage_dict()

                data_object = weaviate.classes.data.DataObject(
                    uuid=entity.db_entity_id,
                    properties=entity_data,
                )
                objects_to_insert.append(data_object)

            # Bulk insert using modern client
            response = await collection.data.insert_many(objects_to_insert)

            if response.errors != {}:
                raise Exception("Errors during bulk insert: %s", str(response.errors))

    async def delete(self, db_entity_id: UUID) -> None:
        """Delete a single entity from Weaviate.

        Args:
            db_entity_id (UUID): The ID of the entity to delete.
        """
        async with WeaviateService(
            weaviate_cluster_url=self.cluster_url,
            weaviate_api_key=self.api_key,
            embedding_model=self.embedding_model,
        ) as service:
            collection = await service.get_weaviate_collection(self.collection_name)
            await collection.data.delete_by_id(uuid=db_entity_id)

    async def bulk_delete(self, entity_ids: list[str]) -> None:
        """Bulk delete entities from Weaviate.

        Args:
            entity_ids (list[str]): The IDs of the entities to delete.
        """
        if not entity_ids:
            return

        async with WeaviateService(
            weaviate_cluster_url=self.cluster_url,
            weaviate_api_key=self.api_key,
            embedding_model=self.embedding_model,
        ) as service:
            collection = await service.get_weaviate_collection(self.collection_name)

            for entity_id in entity_ids:
                try:
                    # Delete the entity by UUID
                    await collection.data.delete_by_id(uuid=entity_id)
                except Exception as e:
                    if "not found" not in str(e).lower():
                        raise

    async def bulk_delete_by_parent_id(self, parent_id: str, sync_id: str) -> None:
        """Bulk delete entities from Weaviate by parent ID and optionally sync ID.

        This deletes all entities that have the specified parent_entity_id and sync_id.

        Args:
            parent_id (str): The parent ID to delete children for.
            sync_id (str, optional): The sync ID.
        """
        if not self.embedding_model or not parent_id:
            return

        async with WeaviateService(
            weaviate_cluster_url=self.cluster_url,
            weaviate_api_key=self.api_key,
            embedding_model=self.embedding_model,
        ) as service:
            collection = await service.get_weaviate_collection(self.collection_name)

            # In v4, the & operator is used for AND operations between filters
            where_filter = Filter.by_property("parent_entity_id").equal(
                parent_id
            ) & Filter.by_property("sync_id").equal(sync_id)

            # Delete all matching entities
            await collection.data.delete_many(where=where_filter)

    async def search(self, query_text: str, sync_id: UUID) -> list[dict]:
        """Search for a sync_id in the destination.

        Args:
            query_text (str): The query text to search for.
            sync_id (UUID): The sync_id to search for.

        Returns:
            list[dict]: The search results.
        """
        # This method searches for entities with the specified sync_id
        async with WeaviateService(
            weaviate_cluster_url=self.cluster_url,
            weaviate_api_key=self.api_key,
            embedding_model=self.embedding_model,
        ) as service:
            collection: Collection = await service.get_weaviate_collection(self.collection_name)

            # Create a proper filter to find all entities with this sync_id
            results = await collection.query.near_text(
                query=query_text,
                limit=10,
                filters=Filter.by_property("sync_id").equal(str(sync_id)),
            )
            return results

    @staticmethod
    def _sanitize_collection_name(collection_name: UUID) -> str:
        """Sanitize the collection name to be a valid Weaviate collection name.

        Args:
            collection_name (UUID): The collection name to sanitize.

        Returns:
            str: The sanitized collection name.
        """
        return str(collection_name).replace("-", "_")
