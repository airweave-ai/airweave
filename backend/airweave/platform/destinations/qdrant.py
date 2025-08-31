"""Qdrant destination implementation."""

from typing import Literal, Optional
from uuid import UUID

from fastembed import SparseEmbedding
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as rest
from qdrant_client.local.local_collection import DEFAULT_VECTOR_NAME

from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.configs.auth import QdrantAuthConfig
from airweave.platform.decorators import destination
from airweave.platform.destinations._base import VectorDBDestination
from airweave.platform.entities._base import ChunkEntity
from airweave.search.decay import DecayConfig

KEYWORD_VECTOR_NAME = "bm25"


@destination("Qdrant", "qdrant", AuthType.config_class, "QdrantAuthConfig", labels=["Vector"])
class QdrantDestination(VectorDBDestination):
    """Qdrant destination implementation.

    This class directly interacts with the Qdrant client and assumes entities
    already have vector embeddings.
    """

    def __init__(self):
        """Initialize Qdrant destination."""
        super().__init__()  # Initialize base class for logger support
        self.collection_name: str | None = None
        self.collection_id: UUID | None = None
        self.url: str | None = None
        self.api_key: str | None = None
        self.client: AsyncQdrantClient | None = None
        self.vector_size: int = 384  # Default vector size

    @classmethod
    async def create(
        cls, collection_id: UUID, logger: Optional[ContextualLogger] = None
    ) -> "QdrantDestination":
        """Create a new Qdrant destination.

        Args:
            collection_id (UUID): The ID of the collection.
            vector_size (int): The size of the vectors to use.
            logger (Optional[ContextualLogger]): The logger to use.

        Returns:
            QdrantDestination: The created destination.
        """
        if not settings.QDRANT_ENABLED:
            raise ConnectionError("Qdrant services are disabled in this deployment")
            
        instance = cls()
        instance.set_logger(logger or default_logger)
        instance.collection_id = collection_id
        instance.collection_name = str(collection_id)

        # Get credentials for sync_id
        credentials = await cls.get_credentials()
        if credentials:
            instance.url = credentials.url
            instance.api_key = credentials.api_key
        else:
            instance.url = None
            instance.api_key = None

        # Initialize client
        await instance.connect_to_qdrant()

        return instance

    @classmethod
    async def get_credentials(cls) -> QdrantAuthConfig | None:
        """Get credentials for the destination.

        Returns:
            QdrantAuthConfig | None: The credentials for the destination.
        """
        # TODO: Implement this
        return None

    async def connect_to_qdrant(self) -> None:
        """Connect to Qdrant service with appropriate authentication."""
        if not settings.QDRANT_ENABLED:
            raise ConnectionError("Qdrant services are disabled in this deployment")
            
        if self.client is None:
            try:
                # Configure client
                if self.url:
                    location = self.url
                else:
                    location = settings.qdrant_url

                client_config = {
                    "location": location,
                    "prefer_grpc": False,  # Use HTTP by default
                }

                if location[-4:] != ":6333":
                    # allow railway to work
                    client_config["port"] = None

                # Add API key if provided
                api_key = self.api_key
                if api_key:
                    client_config["api_key"] = api_key

                # Initialize client
                self.client = AsyncQdrantClient(**client_config)

                # Test connection
                await self.client.get_collections()
                self.logger.debug("Successfully connected to Qdrant service.")
            except Exception as e:
                self.logger.error(f"Error connecting to Qdrant service at {location}: {e}")
                self.client = None
                # Provide more specific error messages
                if "connection refused" in str(e).lower():
                    raise ConnectionError(
                        f"Qdrant service is not running or refusing connections at {location}"
                    ) from e
                elif "timeout" in str(e).lower():
                    raise ConnectionError(
                        f"Connection to Qdrant service timed out at {location}"
                    ) from e

                elif "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                    raise ConnectionError(
                        f"Authentication failed for Qdrant service at {location}"
                    ) from e
                else:
                    raise ConnectionError(
                        f"Failed to connect to Qdrant service at {location}: {str(e)}"
                    ) from e

    def _check_qdrant_enabled(self) -> None:
        """Check if Qdrant is enabled and raise error if not."""
        if not settings.QDRANT_ENABLED:
            raise ConnectionError("Qdrant services are disabled in this deployment")

    async def ensure_client_readiness(self) -> None:
        """Ensure the client is ready to accept requests."""
        self._check_qdrant_enabled()
        if self.client is None:
            await self.connect_to_qdrant()
            if self.client is None:
                raise ConnectionError(
                    "Failed to establish connection to Qdrant service. Please check if "
                    "the service is running and accessible."
                )

    async def close_connection(self) -> None:
        """Close the connection to the Qdrant service."""
        if self.client:
            self.logger.debug("Closing Qdrant client connection gracefully...")
            # Qdrant client doesn't have an explicit close method, but we can set it to None
            self.client = None
        else:
            self.logger.debug("No Qdrant client connection to close.")

    async def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists in Qdrant.

        Args:
            collection_name (str): The name of the collection.

        Returns:
            bool: True if the collection exists, False otherwise.
        """
        self._check_qdrant_enabled()
        await self.ensure_client_readiness()
        try:
            collections_response = await self.client.get_collections()
            collections = collections_response.collections
            return any(collection.name == collection_name for collection in collections)
        except Exception as e:
            self.logger.error(f"Error checking if collection exists: {e}")
            raise  # Re-raise the exception instead of returning False

    async def setup_collection(self, vector_size: int) -> None:  # noqa: C901
        """Set up the Qdrant collection for storing entities.

        Args:
            vector_size (int): The size of the vectors to use.
        """
        self._check_qdrant_enabled()
        await self.ensure_client_readiness()

        try:
            # Check if collection exists
            if await self.collection_exists(self.collection_name):
                self.logger.debug(f"Collection {self.collection_name} already exists.")
                return

            self.logger.info(f"Creating collection {self.collection_name}...")

            # Create the collection
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    # Existing collections will have the default vector config,
                    # so we should tick to it even for new collections.
                    # Annoyingly, the DEFAULT_VECTOR_NAME is an empty string.
                    # Source: https://python-client.qdrant.tech/_modules/qdrant_client/local/local_collection
                    DEFAULT_VECTOR_NAME: rest.VectorParams(
                        size=vector_size if vector_size else self.vector_size,
                        distance=rest.Distance.COSINE,
                    ),
                },
                sparse_vectors_config={
                    KEYWORD_VECTOR_NAME: rest.SparseVectorParams(
                        modifier=rest.Modifier.IDF,
                    )
                },
                optimizers_config=rest.OptimizersConfigDiff(
                    indexing_threshold=20000,  # Default indexing threshold
                ),
                on_disk_payload=True,  # Store payload on disk to save memory
            )

            # Create range indexes for timestamp fields to enable order_by operations
            # These are required for the RecencyBias operator to fetch min/max timestamps
            self.logger.debug(
                f"Creating range indexes for timestamp fields in {self.collection_name}..."
            )

            # Index for harmonized updated_at timestamp (primary field for recency)
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="airweave_system_metadata.airweave_updated_at",
                field_schema=rest.PayloadSchemaType.DATETIME,
            )

            # Index for harmonized created_at timestamp (fallback field)
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="airweave_system_metadata.airweave_created_at",
                field_schema=rest.PayloadSchemaType.DATETIME,
            )

        except Exception as e:
            if "already exists" not in str(e):
                raise

    async def insert(self, entity: ChunkEntity) -> None:
        """Insert a single entity into Qdrant.

        Args:
            entity (ChunkEntity): The entity to insert.
        """
        self._check_qdrant_enabled()
        await self.ensure_client_readiness()

        # Use the entity's to_storage_dict method to get properly serialized data
        data_object = entity.to_storage_dict()

        # Get vector from system metadata
        if not entity.airweave_system_metadata or not entity.airweave_system_metadata.vectors:
            raise ValueError(f"Entity {entity.entity_id} has no vector in system metadata")

        # Get db_entity_id from system metadata
        if not entity.airweave_system_metadata.db_entity_id:
            raise ValueError(f"Entity {entity.entity_id} has no db_entity_id in system metadata")

        # Insert point with vector from entity
        await self.client.upsert(
            collection_name=self.collection_name,
            points=[
                rest.PointStruct(
                    id=str(entity.airweave_system_metadata.db_entity_id),
                    vector={
                        DEFAULT_VECTOR_NAME: entity.airweave_system_metadata.vectors[0],
                    }
                    | (
                        {
                            KEYWORD_VECTOR_NAME: entity.airweave_system_metadata.vectors[
                                1
                            ].as_object(),
                        }
                        if entity.airweave_system_metadata.vectors[1] is not None
                        else {}
                    ),
                    payload=data_object,
                )
            ],
            wait=True,  # Wait for operation to complete
        )

    async def bulk_insert(self, entities: list[ChunkEntity]) -> None:
        """Bulk insert entities into Qdrant.

        Args:
            entities (list[ChunkEntity]): The entities to insert.
        """
        if not entities:
            return

        self._check_qdrant_enabled()
        await self.ensure_client_readiness()

        # Convert entities to Qdrant points
        point_structs = []
        for entity in entities:
            # Use the entity's to_storage_dict method to get properly serialized data
            entity_data = entity.to_storage_dict()

            # Check system metadata exists
            if not entity.airweave_system_metadata:
                raise ValueError(f"Entity {entity.entity_id} has no system metadata")

            # Get vector from system metadata
            if not entity.airweave_system_metadata.vectors:
                raise ValueError(f"Entity {entity.entity_id} has no vector in system metadata")

            if "vectors" in entity_data["airweave_system_metadata"]:
                entity_data["airweave_system_metadata"].pop("vectors")

            # Create point for Qdrant
            point_structs.append(
                rest.PointStruct(
                    id=str(entity.airweave_system_metadata.db_entity_id),
                    vector={
                        DEFAULT_VECTOR_NAME: entity.airweave_system_metadata.vectors[0],
                    }
                    | (
                        {
                            KEYWORD_VECTOR_NAME: entity.airweave_system_metadata.vectors[
                                1
                            ].as_object(),
                        }
                        if entity.airweave_system_metadata.vectors[1] is not None
                        else {}
                    ),
                    payload=entity_data,
                )
            )

        if not point_structs:
            self.logger.warning("No valid entities to insert")
            return

        # Bulk upsert
        operation_response = await self.client.upsert(
            collection_name=self.collection_name,
            points=point_structs,
            wait=True,  # Wait for operation to complete
        )

        if hasattr(operation_response, "errors") and operation_response.errors:
            raise Exception(f"Errors during bulk insert: {operation_response.errors}")

    async def delete(self, db_entity_id: UUID) -> None:
        """Delete a single entity from Qdrant.

        Args:
            db_entity_id (UUID): The ID of the entity to delete.
        """
        self._check_qdrant_enabled()
        await self.ensure_client_readiness()

        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest.PointIdsList(
                points=[str(db_entity_id)],
            ),
            wait=True,  # Wait for operation to complete
        )

    async def delete_by_sync_id(self, sync_id: UUID) -> None:
        """Delete entities from the destination by sync ID."""
        self._check_qdrant_enabled()
        await self.ensure_client_readiness()

        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest.FilterSelector(
                filter=rest.Filter(
                    should=[
                        rest.FieldCondition(
                            key="airweave_system_metadata.sync_id",
                            match=rest.MatchValue(value=str(sync_id)),
                        )
                    ]
                )
            ),
            wait=True,  # Wait for operation to complete
        )

    async def bulk_delete(self, entity_ids: list[str], sync_id: UUID) -> None:
        """Bulk delete entities from Qdrant.

        Args:
            entity_ids (list[str]): The IDs of the entities to delete.
            sync_id (UUID): The sync ID.
        """
        if not entity_ids:
            return

        self._check_qdrant_enabled()
        await self.ensure_client_readiness()

        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest.FilterSelector(
                filter=rest.Filter(
                    must=[
                        rest.FieldCondition(
                            key="airweave_system_metadata.sync_id",
                            match=rest.MatchValue(value=str(sync_id)),
                        ),
                        rest.FieldCondition(key="entity_id", match=rest.MatchAny(any=entity_ids)),
                    ]
                )
            ),
            wait=True,  # Wait for operation to complete
        )

    async def bulk_delete_by_parent_id(self, parent_id: str, sync_id: str) -> None:
        """Bulk delete entities from Qdrant by entity ID, parent entity IDand sync ID.

        This deletes all entities that have the specified parent_entity_id and sync_id.

        Args:
            parent_id (str): The parent ID to delete children for.
            sync_id (str): The sync ID.
        """
        if not parent_id:
            return

        self._check_qdrant_enabled()
        await self.ensure_client_readiness()

        # Ensure sync_id is a string
        sync_id_str = str(sync_id)
        parent_id_str = str(parent_id)

        # Create filter using Qdrant SDK objects directly
        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest.FilterSelector(
                filter=rest.Filter(
                    must=[
                        rest.FieldCondition(
                            key="parent_entity_id", match=rest.MatchValue(value=parent_id_str)
                        ),
                        rest.FieldCondition(
                            key="airweave_system_metadata.sync_id",
                            match=rest.MatchValue(value=sync_id_str),
                        ),
                    ]
                )
            ),
            wait=True,  # Wait for operation to complete
        )

    def _prepare_index_search_request(
        self,
        params: dict,
        decay_config: Optional[DecayConfig] = None,
    ) -> dict:
        """Prepare a query request for Qdrant.

        If decay is enabled, we need to use prefetch + formula query pattern in order to
        bias the result wrt to the decay score, otherwise we just return the params as is
        (since the query does not need to be prefetched or have a custom formula applied
        to it in that case).

        Args:
            params (dict): The parameters for the query request.
            decay_config (Optional[DecayConfig]): Configuration for time-based decay.
                If None, no decay is applied.

        Returns:
            dict: The prepared query request.
        """
        if decay_config is None:
            return params

        scale_seconds = decay_config.get_scale_seconds()
        decay_params = rest.DecayParamsExpression(
            x=rest.DatetimeKeyExpression(datetime_key=decay_config.datetime_field),
            target=rest.DatetimeExpression(datetime=decay_config.target_datetime.isoformat()),
            scale=scale_seconds,
            midpoint=decay_config.midpoint,
        )

        decay_expressions = {
            "linear": lambda p: rest.LinDecayExpression(lin_decay=p),
            "exponential": lambda p: rest.ExpDecayExpression(exp_decay=p),
            "gaussian": lambda p: rest.GaussDecayExpression(gauss_decay=p),
        }

        decay_expression = decay_expressions[decay_config.decay_type](decay_params)

        # Decay returns 0-1 (1=newest, 0=oldest)
        # We want to multiply scores by a factor that boosts newer items
        # With weight=1.0, newest items get full score, oldest get 0
        # With weight=0.5, newest get full score, oldest get 0.5*score
        weight = getattr(decay_config, "weight", 1.0) if decay_config else 1.0

        if weight <= 0.0:
            # No recency bias
            weighted_formula = "$score"
        elif weight >= 1.0:
            # Full recency: rank by recency only within candidate set
            # This ignores similarity entirely
            weighted_formula = decay_expression
        else:
            # Partial recency: blend similarity and decay proportionally
            # Since we can't predict RRF score range (could be 0.03 to 20+),
            # we use a multiplicative approach that works regardless of scale:
            # score * (1 - weight + weight * decay)
            # This ensures:
            # - Newest items (decay=1): score * 1.0 (full score)
            # - Oldest items (decay=0): score * (1-weight) (reduced score)
            # - Mid-age items scale linearly between these

            decay_factor = rest.SumExpression(
                sum=[
                    1.0 - weight,  # Base multiplier for all items
                    rest.MultExpression(
                        mult=[weight, decay_expression]
                    ),  # Additional boost for newer items
                ]
            )
            weighted_formula = rest.MultExpression(mult=["$score", decay_factor])

        # Log the formula composition for transparency
        try:
            self.logger.debug(
                f"[Qdrant] Decay formula applied: using={params.get('using')}, "
                f"weight={weight}, field={decay_config.datetime_field}"
            )
        except Exception:
            pass

        return {
            "prefetch": rest.Prefetch(**params),
            "query": rest.FormulaQuery(formula=weighted_formula),
        }

    async def _prepare_query_request(
        self,
        query_vector: list[float],
        limit: int,
        sparse_vector: SparseEmbedding | None,
        search_method: Literal["hybrid", "neural", "keyword"],
        decay_config: Optional[DecayConfig] = None,
    ) -> rest.QueryRequest:
        """Prepare a query request for Qdrant.

        Args:
            query_vector (list[float]): The query vector to search with.
            limit (int): Maximum number of results to return.
            sparse_vector (SparseEmbedding | None): Optional sparse vector to search with.
            search_method (Literal["hybrid", "neural", "keyword"]): The search method to use.
            decay_config (Optional[DecayConfig]): Configuration for time-based decay.
                If None, no decay is applied.

        Returns:
            rest.QueryRequest: The prepared query request.
        """
        query_request_params = {}

        if search_method == "neural":
            neural_params = {
                "query": query_vector,
                "using": DEFAULT_VECTOR_NAME,
                "limit": limit,
            }
            query_request_params = self._prepare_index_search_request(
                params=neural_params,
                decay_config=decay_config,
            )

        if search_method == "keyword":
            if not sparse_vector:
                raise ValueError("Keyword search requires sparse vector")

            keyword_params = {
                "query": rest.SparseVector(**sparse_vector.as_object()),
                "using": KEYWORD_VECTOR_NAME,
                "limit": limit,
            }
            query_request_params = self._prepare_index_search_request(
                params=keyword_params,
                decay_config=decay_config,
            )

        if search_method == "hybrid":
            if not sparse_vector:
                raise ValueError("Hybrid search requires sparse vector")

            # Use a large prefetch limit to ensure recency can work across a broad candidate set
            # Optional: scale based on recency bias strength
            prefetch_limit = 10000  # Large fixed limit for good recency coverage
            if decay_config is not None:
                try:
                    weight = max(0.0, min(1.0, float(getattr(decay_config, "weight", 0.0) or 0.0)))
                    # Optional heuristic: increase prefetch with higher recency bias
                    # At weight=0.3: 10k, at weight=0.7: 15k, at weight=1.0: 20k
                    if weight > 0.3:
                        prefetch_limit = int(10000 * (1 + weight))
                except Exception:
                    pass

            prefetch_params = [
                # Neural embedding
                {
                    "query": query_vector,
                    "using": DEFAULT_VECTOR_NAME,
                    "limit": prefetch_limit,
                },
                # BM25 embedding
                {
                    "query": rest.SparseVector(**sparse_vector.as_object()),
                    "using": KEYWORD_VECTOR_NAME,
                    "limit": prefetch_limit,
                },
            ]

            # Always do prefetch without decay first to get similarity-based candidates
            prefetches = [rest.Prefetch(**params) for params in prefetch_params]

            if decay_config is None or decay_config.weight <= 0.0:
                # No decay, just use RRF fusion
                query_request_params = {
                    "prefetch": prefetches,
                    "query": rest.FusionQuery(fusion=rest.Fusion.RRF),
                }
            else:
                # Apply decay AFTER fusion using nested prefetch pattern
                # Step 1: Create the RRF fusion prefetch (this will be normalized)
                rrf_prefetch = rest.Prefetch(
                    prefetch=prefetches,  # List of prefetches to fuse
                    query=rest.FusionQuery(fusion=rest.Fusion.RRF),
                    limit=prefetch_limit,  # Large limit for good candidate pool
                )

                # Step 2: Apply decay formula to the normalized RRF results
                decay_params = self._prepare_index_search_request(
                    params={},  # Empty params since we're applying to fused results
                    decay_config=decay_config,
                )

                # Use nested prefetch to ensure normalization happens before decay
                query_request_params = {
                    "prefetch": [rrf_prefetch],  # Single prefetch with RRF fusion
                    "query": decay_params["query"],  # Apply decay formula to normalized results
                }

        return rest.QueryRequest(
            **query_request_params,
        )

    def _validate_bulk_search_inputs(
        self,
        query_vectors: list[list[float]],
        filter_conditions: list[dict] | None,
        sparse_vectors: list[SparseEmbedding] | None,
    ) -> None:
        """Validate inputs for bulk search operation.

        Args:
            query_vectors (list[list[float]]): List of query vectors to search with.
            filter_conditions (list[dict] | None): Optional list of filter conditions.
            sparse_vectors (list[SparseEmbedding] | None): Optional list of sparse vectors.

        Raises:
            ValueError: If inputs are invalid.
        """
        if filter_conditions and len(filter_conditions) != len(query_vectors):
            raise ValueError(
                f"Number of filter conditions ({len(filter_conditions)}) must match "
                f"number of query vectors ({len(query_vectors)})"
            )

        if sparse_vectors and len(query_vectors) != len(sparse_vectors):
            raise ValueError("Sparse vector count does not match query vectors")

    async def _prepare_bulk_search_requests(
        self,
        query_vectors: list[list[float]],
        limit: int,
        score_threshold: float | None,
        with_payload: bool,
        filter_conditions: list[dict] | None,
        sparse_vectors: list[SparseEmbedding] | None,
        search_method: Literal["hybrid", "neural", "keyword"],
        decay_config: Optional[DecayConfig],
        offset: Optional[int],
    ) -> list[rest.QueryRequest]:
        """Prepare query requests for bulk search.

        Args:
            query_vectors (list[list[float]]): List of query vectors to search with.
            limit (int): Maximum number of results per query.
            score_threshold (float | None): Optional minimum score threshold.
            with_payload (bool): Whether to include payload in results.
            filter_conditions (list[dict] | None): Optional list of filter conditions.
            sparse_vectors (list[SparseEmbedding] | None): Optional list of sparse vectors.
            search_method (Literal["hybrid", "neural", "keyword"]): The search method to use.
            decay_config (Optional[DecayConfig]): Configuration for time-based decay.
            If None, no decay is applied.
            offset (Optional[int]): Number of results to skip.

        Returns:
            list[rest.QueryRequest]: List of prepared query requests.
        """
        query_requests = []
        for i, query_vector in enumerate(query_vectors):
            sparse_vector = sparse_vectors[i] if sparse_vectors else None

            request = await self._prepare_query_request(
                query_vector=query_vector,
                limit=limit,
                sparse_vector=sparse_vector,
                search_method=search_method,
                decay_config=decay_config,
            )

            # Add filter if provided
            if filter_conditions and filter_conditions[i]:
                request.filter = rest.Filter.model_validate(filter_conditions[i])

            # Add optional parameters
            if offset and offset > 0:
                request.offset = offset

            # Add score threshold if provided
            if score_threshold is not None:
                request.score_threshold = score_threshold

            # Include payload
            request.with_payload = with_payload

            query_requests.append(request)

        return query_requests

    def _format_bulk_search_results(
        self, batch_results: list, with_payload: bool
    ) -> list[list[dict]]:
        """Format batch search results into standard format.

        Args:
            batch_results (list): Raw batch search results from Qdrant.
            with_payload (bool): Whether to include payload in results.

        Returns:
            list[list[dict]]: Formatted search results.
        """
        all_results = []
        for search_results in batch_results:
            results = []
            for result in search_results.points:
                result_dict = {
                    "id": result.id,
                    "score": result.score,
                }
                if with_payload:
                    result_dict["payload"] = result.payload
                results.append(result_dict)
            all_results.append(results)

        return all_results

    async def search(
        self,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: float | None = None,
        with_payload: bool = True,
        filter: dict | None = None,
        decay_config: Optional[DecayConfig] = None,
        sparse_vector: SparseEmbedding | None = None,
        search_method: Literal["hybrid", "neural", "keyword"] = "hybrid",
        offset: int = 0,
    ) -> list[dict]:
        """Search for entities in the destination.

        Args:
            query_vector (list[float]): The query vector to search with.
            limit (int): Maximum number of results to return.
            score_threshold (float | None): Optional minimum score threshold.
            with_payload (bool): Whether to include payload in results.
            filter (dict | None): Optional filter conditions as a dictionary.
            decay_config (Optional[DecayConfig]): Configuration for time-based decay.
                If None, no decay is applied.
            sparse_vector (SparseEmbedding | None): Optional sparse vector to search with.
            search_method (Literal["hybrid", "neural", "keyword"]): The search method to use.
            offset (int): Number of results to skip.

        Returns:
            list[dict]: The search results.
        """
        return await self.bulk_search(
            query_vectors=[query_vector],
            limit=limit,
            score_threshold=score_threshold,
            with_payload=with_payload,
            filter_conditions=[filter] if filter else None,
            sparse_vectors=[sparse_vector] if sparse_vector else None,
            search_method=search_method,
            decay_config=decay_config,
            offset=offset,
        )

    async def bulk_search(
        self,
        query_vectors: list[list[float]],
        limit: int = 10,
        score_threshold: float | None = None,
        with_payload: bool = True,
        filter_conditions: list[dict] | None = None,
        sparse_vectors: list[SparseEmbedding] | None = None,
        search_method: Literal["hybrid", "neural", "keyword"] = "hybrid",
        decay_config: Optional[DecayConfig] = None,
        offset: Optional[int] = None,
    ) -> list[dict]:
        """Perform batch search for multiple query vectors in a single request.

        Args:
            query_vectors (list[list[float]]): List of query vectors to search with.
            limit (int): Maximum number of results per query. Defaults to 10.
            score_threshold (float | None): Optional minimum score threshold for results.
            with_payload (bool): Whether to include payload in results. Defaults to True.
            filter_conditions (list[dict] | None): Optional list of filter conditions,
                one per query vector. If provided, must have same length as query_vectors.
            sparse_vectors (List[SparseEmbedding] | None): Optional list of sparse vectors.
                If provided, must have same length as query_vectors.
            search_method (Literal["hybrid", "neural", "keyword"]): The search method to use.
                Defaults to "hybrid".
            decay_config (Optional[DecayConfig]): Configuration for time-based decay.
                If None, no decay is applied.
            offset (Optional[int]): Number of results to skip.

        Returns:
            list[list[dict]]: List of search results for each query vector.
                Each inner list contains results for the corresponding query vector.
        """
        self._check_qdrant_enabled()
        await self.ensure_client_readiness()

        if not query_vectors:
            return []

        # Validate inputs
        self._validate_bulk_search_inputs(query_vectors, filter_conditions, sparse_vectors)

        # Fallback to neural search if BM25 index does not exist
        vector_config_names = await self.get_vector_config_names()
        if KEYWORD_VECTOR_NAME not in vector_config_names:
            self.logger.warning(
                f"{KEYWORD_VECTOR_NAME} index could not be found in "
                f"collection {self.collection_name}. "
                f"Using neural search instead."
            )
            search_method = "neural"

        # Log search configuration at Qdrant level
        weight = getattr(decay_config, "weight", None) if decay_config else None
        self.logger.info(
            f"[Qdrant] Executing {search_method.upper()} search: "
            f"queries={len(query_vectors)}, limit={limit}, "
            f"has_sparse={sparse_vectors is not None}, "
            f"decay_enabled={decay_config is not None}, "
            f"decay_weight={weight}"
        )

        if decay_config:
            weight_val = getattr(decay_config, "weight", 0)
            strategy = (
                "Pure recency (RRF then decay)"
                if weight_val >= 1.0
                else "RRF fusion THEN decay applied"
            )
            self.logger.debug(
                f"[Qdrant] Decay strategy: weight={weight_val:.1f} - {strategy}, "
                f"field={decay_config.datetime_field}, scale={decay_config.scale_value}s"
            )

        try:
            # Prepare query requests
            query_requests = await self._prepare_bulk_search_requests(
                query_vectors=query_vectors,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=with_payload,
                filter_conditions=filter_conditions,
                sparse_vectors=sparse_vectors,
                search_method=search_method,
                decay_config=decay_config,
                offset=offset,
            )

            # Perform batch search
            batch_results = await self.client.query_batch_points(
                collection_name=self.collection_name, requests=query_requests
            )

            # Format and return results
            formatted_results = self._format_bulk_search_results(batch_results, with_payload)

            # Flatten results from all queries
            flattened_results = []
            for query_results in formatted_results:
                flattened_results.extend(query_results)

            # Log score statistics to show hybrid search impact
            if flattened_results:
                scores = [r.get("score", 0) for r in flattened_results if isinstance(r, dict)]
                if scores:
                    avg_score = sum(scores) / len(scores)
                    max_score = max(scores)
                    min_score = min(scores)

                    if decay_config:
                        # Calculate score distribution in quartiles
                        sorted_scores = sorted(scores, reverse=True)
                        q1_idx = len(sorted_scores) // 4
                        q2_idx = len(sorted_scores) // 2
                        q3_idx = 3 * len(sorted_scores) // 4

                        q1_score = sorted_scores[q1_idx] if q1_idx < len(sorted_scores) else 0
                        q2_score = sorted_scores[q2_idx] if q2_idx < len(sorted_scores) else 0
                        q3_score = sorted_scores[q3_idx] if q3_idx < len(sorted_scores) else 0

                        self.logger.debug(
                            f"[Qdrant] Result scores with {search_method} search + RECENCY "
                            f"(weight={decay_config.weight}): count={len(scores)}, "
                            f"avg={avg_score:.3f}, max={max_score:.3f}, Q1={q1_score:.3f}, "
                            f"median={q2_score:.3f}, Q3={q3_score:.3f}, min={min_score:.3f}"
                        )
                    else:
                        self.logger.debug(
                            f"[Qdrant] Result scores with {search_method} search (NO recency): "
                            f"count={len(scores)}, avg={avg_score:.3f}, "
                            f"max={max_score:.3f}, min={min_score:.3f}"
                        )

            return flattened_results

        except Exception as e:
            self.logger.error(f"Error performing batch search with Qdrant: {e}")
            raise

    async def has_keyword_index(self) -> bool:
        """Check if the destination has a keyword index."""
        self._check_qdrant_enabled()
        vector_config_names = await self.get_vector_config_names()
        return KEYWORD_VECTOR_NAME in vector_config_names

    async def get_vector_config_names(self) -> list[str]:
        """Get the names of all vector configurations (both dense and sparse) for the collection.

        Returns:
            list[str]: A list of vector configuration names from the collection.
                Includes both dense vector configs and sparse vector configs.
        """
        self._check_qdrant_enabled()
        await self.ensure_client_readiness()

        try:
            # Get collection info
            collection_info = await self.client.get_collection(collection_name=self.collection_name)

            vector_config_names = []

            # Get dense vector config names
            if collection_info.config.params.vectors:
                if isinstance(collection_info.config.params.vectors, dict):
                    # Named vectors configuration
                    vector_config_names.extend(collection_info.config.params.vectors.keys())
                else:
                    # Single vector configuration (uses default name)
                    vector_config_names.append(DEFAULT_VECTOR_NAME)

            # Get sparse vector config names
            if collection_info.config.params.sparse_vectors:
                vector_config_names.extend(collection_info.config.params.sparse_vectors.keys())

            return vector_config_names

        except Exception as e:
            self.logger.error(
                f"Error getting vector configurations from collection {self.collection_name}: {e}"
            )
            raise
