"""Service class for managing a connection to a Weaviate cluster."""

import traceback as tb
from typing import Optional

import weaviate
from weaviate.classes.init import Auth
from weaviate.client import WeaviateAsyncClient
from weaviate.collections import Collection
from weaviate.collections.classes.config import GenerativeConfig, Property, VectorizerConfig

from airweave.core.exceptions import NotFoundException
from airweave.core.logging import logger
from airweave.platform.embedding_models._base import BaseEmbeddingModel


class WeaviateService:
    """Service for configuring, setting up, and terminating a connection to a Weaviate Cluster.

    Attributes:
    ----------
        weaviate_cluster_url (str): The URL of the Weaviate cluster.
        weaviate_api_key (str): The API key for Weaviate.
        client (WeaviateClient): The client instance for interacting with the Weaviate cluster.

    Example usage:
    ```python
    async with WeaviateService() as weaviate_service:
        collection = await weaviate_service.create_weaviate_collection(
            collection_name="my-collection",
            properties=[
                wvc.Property(name="name", data_type=wvc.DataType.STRING),
                wvc.Property(name="description", data_type=wvc.DataType.TEXT),
            ],
        )
    ```

    """

    def __init__(
        self,
        weaviate_cluster_url: Optional[str] = None,
        weaviate_api_key: Optional[str] = None,
        embedding_model: Optional[BaseEmbeddingModel] = None,
    ) -> None:
        """Initialize the WeaviateService with configurable settings.

        Args:
        ----
            weaviate_cluster_url (Optional[str]): The URL of the Weaviate cluster.
            weaviate_api_key (Optional[str]): The API key for Weaviate.
            embedding_model (Optional[BaseEmbeddingModel]): The embedding model to use.
        """
        self.weaviate_cluster_url: str = weaviate_cluster_url
        self.weaviate_api_key: str = weaviate_api_key
        self.embedding_model: BaseEmbeddingModel = embedding_model
        self.client: Optional[WeaviateAsyncClient] = None

        return None

    async def __aenter__(self):
        """Async context manager to connect to the Weaviate cluster.

        Returns:
        -------
            WeaviateService: The WeaviateService instance

        """
        await self.connect_to_weaviate_cluster()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[tb.TracebackException],
    ) -> None:
        """Async context manager to close the connection to the Weaviate cluster.

        Propagates any exceptions that occur during the context by returning None.

        Args:
        ----
            exc_type (Optional[Type[BaseException]]): The exception type if an exception was raised
                in the context.
            exc_value (Optional[BaseException]): The exception instance if an exception was raised.
            traceback (Optional[TracebackType]): Traceback object if an exception was raised.

        """
        try:
            await self.close_connection()
        finally:
            if exc_type is not None:
                logger.error(
                    "An error occurred during an open Weaviate connection: %s",
                    exc_value,
                    exc_info=(exc_type, exc_value, traceback),
                )

    async def get_weaviate_collection(self, collection_name: str) -> Collection | None:
        """Get a Weaviate collection with the specified name.

        Args:
        ----
            collection_name (str): The name of the collection.

        Returns:
        -------
            wvc.Collection: The Weaviate collection instance.

        Raises:
        ------
            NotFoundException: If the collection does not exist.

        """
        if self.client and await self.collection_exists(collection_name):
            return self.client.collections.get(collection_name)
        else:
            logger.info(f"Collection {collection_name} does not exist.")
            raise NotFoundException(f"Collection {collection_name} does not exist.")

    async def create_weaviate_collection(
        self,
        collection_name: str,
        properties: list[Property],
        vectorizer_config: VectorizerConfig,
        generative_config: Optional[GenerativeConfig] = None,
    ) -> Collection:
        """Create a Weaviate collection with configurable vectorizer."""
        await self.ensure_client_readiness()

        if await self.collection_exists(collection_name):
            logger.info(f"Collection {collection_name} already exists.")
            raise Exception(f"Collection {collection_name} already exists.")

        logger.info(f"Creating collection {collection_name} ...")
        if self.client:
            config = {
                "name": collection_name,
                "properties": properties,
                "vectorizer_config": vectorizer_config,
            }

            if generative_config:
                config["generative_config"] = generative_config

            return await self.client.collections.create(**config)

        raise Exception("Weaviate client not initialized")

    async def connect_to_weaviate_cluster(self) -> None:
        """Connect to Weaviate cluster with appropriate authentication."""
        if self.client is None or not await self.client.is_connected():
            try:
                headers = {}
                if self.embedding_model and self.embedding_model.model_name == "openai-text2vec":
                    headers["X-OpenAI-Api-Key"] = self.embedding_model.api_key

                if not self.weaviate_api_key:
                    raise Exception(
                        "Weaviate API key not set. Weaviate used to be Airweave's standard "
                        "local vector database. That is now deprecated. Please use Qdrant."
                    )
                # Cloud deployment with authentication
                self.client = weaviate.use_async_with_weaviate_cloud(
                    cluster_url=self.weaviate_cluster_url,
                    auth_credentials=Auth.api_key(self.weaviate_api_key),
                    additional_headers=headers,
                )

                # Connect the client
                await self.client.connect()
                logger.info("Successfully connected to Weaviate cluster.")
            except Exception as e:
                logger.error(f"Error connecting to Weaviate cluster: {e}")
                self.client = None
                raise

    async def ensure_client_readiness(self) -> None:
        """Ensure the client is ready to accept requests.

        Raises:
        ------
            Exception: If the client is not ready.

        """
        if self.client is None or not self.client.is_connected():
            await self.connect_to_weaviate_cluster()
            if self.client is None or not self.client.is_connected():
                raise Exception("Client failed to connect.")

    async def close_connection(self) -> None:
        """Close the connection to the Weaviate cluster."""
        if self.client:
            logger.info("Closing WeaviateClient connection gracefully  ...")
            await self.client.close()
        else:
            logger.info("No WeaviateClient connection to close.")

    async def collection_exists(self, collection_name: str) -> bool | None:
        """Check if a collection exists in the Weaviate cluster.

        Args:
        ----
            collection_name (str): The name of the collection.

        Returns:
        -------
            bool: True if the collection exists, False otherwise.

        """
        if self.client:
            return await self.client.collections.exists(collection_name)
