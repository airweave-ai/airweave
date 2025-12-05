"""Weaviate destination implementation."""

from __future__ import annotations

import asyncio
from typing import Optional
from uuid import UUID

import weaviate
from weaviate.classes.config import Configure, Property, DataType
from weaviate.classes.query import Filter

from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.platform.configs.auth import WeaviateAuthConfig
from airweave.platform.decorators import destination
from airweave.platform.destinations._base import VectorDBDestination
from airweave.platform.entities._base import BaseEntity


@destination("Weaviate", "weaviate", auth_config_class=WeaviateAuthConfig, supports_vector=True)
class WeaviateDestination(VectorDBDestination):
    """Weaviate destination implementation."""

    def __init__(self):
        """Initialize defaults."""
        super().__init__()
        self.client: weaviate.WeaviateAsyncClient | None = None
        self.collection_name: str | None = None
        self.collection_id: UUID | None = None
        self.vector_size: int = 3072  # Default, will be updated in create/setup

    @classmethod
    async def create(
        cls,
        collection_id: UUID,
        organization_id: Optional[UUID] = None,
        vector_size: Optional[int] = None,
        credentials: Optional[WeaviateAuthConfig] = None,
        config: Optional[dict] = None,
        logger: Optional[ContextualLogger] = None,
    ) -> "WeaviateDestination":
        """Create and return a connected destination."""
        instance = cls()
        instance.set_logger(logger or default_logger)
        instance.collection_id = collection_id
        instance.vector_size = vector_size or 3072
        
        # Weaviate collection names must start with a capital letter and be alphanumeric
        # We'll use a prefix + sanitized collection ID
        sanitized_id = str(collection_id).replace("-", "")
        instance.collection_name = f"Airweave_{sanitized_id}"

        if credentials:
            instance.client = weaviate.use_async_with_params(
                client=weaviate.connect.ConnectionParams.from_params(
                    http_host=credentials.cluster_url.replace("http://", "").replace("https://", "").split(":")[0],
                    http_port=int(credentials.cluster_url.split(":")[-1]) if ":" in credentials.cluster_url else 8080,
                    http_secure=credentials.cluster_url.startswith("https"),
                    grpc_host=credentials.cluster_url.replace("http://", "").replace("https://", "").split(":")[0],
                    grpc_port=50051, # Default gRPC port
                    grpc_secure=credentials.cluster_url.startswith("https"),
                ),
                auth_client_secret=weaviate.auth.AuthApiKey(credentials.api_key) if credentials.api_key else None
            )
        else:
            # Default local connection
            instance.client = weaviate.connect_to_local(
                port=8080,
                grpc_port=50051
            )

        await asyncio.to_thread(instance.client.connect)
        return instance

    async def setup_collection(self, vector_size: int | None = None) -> None:
        """Set up the Weaviate collection."""
        if not self.client.is_connected():
            await asyncio.to_thread(self.client.connect)
            
        if await asyncio.to_thread(self.client.collections.exists, self.collection_name):
            return

        await asyncio.to_thread(
            self.client.collections.create,
            name=self.collection_name,
            vectorizer_config=Configure.Vectorizer.none(),
            properties=[
                Property(name="text", data_type=DataType.TEXT),
                Property(name="source_id", data_type=DataType.UUID),
                Property(name="sync_id", data_type=DataType.UUID),
                Property(name="entity_id", data_type=DataType.TEXT),
                Property(name="url", data_type=DataType.TEXT),
                Property(name="metadata", data_type=DataType.TEXT),
            ]
        )

    async def insert(self, entity: BaseEntity) -> None:
        """Insert a single entity."""
        await self.bulk_insert([entity])

    async def bulk_insert(self, entities: list[BaseEntity]) -> None:
        """Bulk insert entities."""
        if not entities:
            return

        if not self.client.is_connected():
            await asyncio.to_thread(self.client.connect)

        collection = self.client.collections.get(self.collection_name)
        
        objects = []
        import json
        for entity in entities:
            if not entity.airweave_system_metadata or not entity.airweave_system_metadata.vectors:
                continue

            props = entity.model_dump(exclude={"airweave_system_metadata"})
            # Flatten metadata for Weaviate or store as JSON object
            
            objects.append(
                weaviate.classes.data.DataObject(
                    properties={
                        "text": entity.textual_representation or entity.name or "",
                        "source_id": str(entity.source_id) if hasattr(entity, "source_id") else None,
                        "sync_id": str(entity.airweave_system_metadata.sync_id),
                        "entity_id": entity.entity_id,
                        "url": entity.url if hasattr(entity, "url") else None,
                        "metadata": json.dumps(props)
                    },
                    vector=entity.airweave_system_metadata.vectors[0]
                )
            )

        await asyncio.to_thread(collection.data.insert_many, objects)

    async def delete(self, db_entity_id: UUID) -> None:
        """Delete a single entity."""
        # Not implemented for this PoC
        pass

    async def bulk_delete(self, entity_ids: list[str], sync_id: UUID) -> None:
        """Bulk delete entities."""
        # Not implemented for this PoC
        pass

    async def delete_by_sync_id(self, sync_id: UUID) -> None:
        """Delete entities by sync ID."""
        if not self.client.is_connected():
            await asyncio.to_thread(self.client.connect)
            
        collection = self.client.collections.get(self.collection_name)
        await asyncio.to_thread(
            collection.data.delete_many,
            where=Filter.by_property("sync_id").equal(str(sync_id))
        )

    async def bulk_delete_by_parent_id(self, parent_id: str, sync_id: UUID) -> None:
        """Delete by parent ID."""
        # Not implemented for this PoC
        pass

    async def search(self, query_vector: list[float]) -> None:
        """Search."""
        # Not implemented for this PoC
        pass

    async def has_keyword_index(self) -> bool:
        """Check for keyword index."""
        return True

    async def get_vector_config_names(self) -> list[str]:
        """Get vector config names."""
        return ["default"]
