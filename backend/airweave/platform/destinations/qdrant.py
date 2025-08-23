"""Qdrant destination implementation."""

import uuid  # <-- for uuid5 deterministic IDs
from typing import Literal, Optional
from uuid import UUID

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
        """Create a new Qdrant destination."""
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
        """Get credentials for the destination."""
        # TODO: Implement this
        return None

    async def connect_to_qdrant(self) -> None:
        """Connect to Qdrant service with appropriate authentication."""
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

    async def ensure_client_readiness(self) -> None:
        """Ensure the client is ready to accept requests."""
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
            self.client = None
        else:
            self.logger.debug("No Qdrant client connection to close.")

    async def collection_exists(self, collection_name: str) -> bool:
        """Check if a collection exists in Qdrant."""
        await self.ensure_client_readiness()
        try:
            collections_response = await self.client.get_collections()
            collections = collections_response.collections
            return any(collection.name == collection_name for collection in collections)
        except Exception as e:
            self.logger.error(f"Error checking if collection exists: {e}")
            raise

    async def setup_collection(self, *args, **kwargs) -> None:  # noqa: C901
        """Set up the Qdrant collection for storing entities.

        Compatible with BOTH call styles:
          - setup_collection(vector_size)
          - setup_collection(collection_id, vector_size)
        """
        # ---- accept both signatures ----
        collection_id: UUID | None = None
        vector_size: Optional[int] = None

        if len(args) == 1:
            vector_size = args[0]
        elif len(args) >= 2:
            collection_id, vector_size = args[0], args[1]
        else:
            vector_size = kwargs.get("vector_size")
            collection_id = kwargs.get("collection_id")

        if vector_size is None:
            raise TypeError("setup_collection() missing required argument: 'vector_size'")

        if collection_id is not None:
            self.collection_id = collection_id
            self.collection_name = str(collection_id)

        await self.ensure_client_readiness()

        if not self.collection_name:
            raise ValueError(
                "QdrantDestination.collection_name is not set. "
                "Ensure create(collection_id, ...) was called before setup_collection()."
            )

        try:
            if await self.collection_exists(self.collection_name):
                self.logger.debug(f"Collection {self.collection_name} already exists.")
                return

            self.logger.info(f"Creating collection {self.collection_name}...")

            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
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
                    indexing_threshold=20000,
                ),
                on_disk_payload=True,
            )

            # Indexes for recency sorting / filters
            self.logger.debug(
                f"Creating range indexes for timestamp fields in {self.collection_name}..."
            )
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="airweave_system_metadata.airweave_updated_at",
                field_schema=rest.PayloadSchemaType.DATETIME,
            )
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="airweave_system_metadata.airweave_created_at",
                field_schema=rest.PayloadSchemaType.DATETIME,
            )

        except Exception as e:
            if "already exists" not in str(e):
                raise

    # ---------- Helper: deterministic UUID point id ----------
    @staticmethod
    def _make_point_uuid(db_entity_id: UUID | str, child_entity_id: str) -> str:
        """Create a deterministic UUIDv5 from (parent db UUID, child entity_id)."""
        ns = UUID(str(db_entity_id)) if not isinstance(db_entity_id, UUID) else db_entity_id
        return str(uuid.uuid5(ns, child_entity_id))

    async def insert(self, entity: ChunkEntity) -> None:
        """Insert a single entity into Qdrant."""
        await self.ensure_client_readiness()

        data_object = entity.to_storage_dict()

        # Safety checks
        if not entity.airweave_system_metadata or not entity.airweave_system_metadata.vectors:
            raise ValueError(f"Entity {entity.entity_id} has no vector in system metadata")
        if not entity.airweave_system_metadata.db_entity_id:
            raise ValueError(f"Entity {entity.entity_id} has no db_entity_id in system metadata")

        # Remove vectors from payload (store vectors in dedicated fields only)
        if "airweave_system_metadata" in data_object and isinstance(
            data_object["airweave_system_metadata"], dict
        ):
            data_object["airweave_system_metadata"].pop("vectors", None)

        # ✅ VALID Qdrant point id (UUID)
        point_id = self._make_point_uuid(
            entity.airweave_system_metadata.db_entity_id, entity.entity_id
        )

        # Prepare sparse vector if present
        sv = (
            entity.airweave_system_metadata.vectors[1]
            if entity.airweave_system_metadata.vectors
            else None
        )
        sparse_part = {}
        if sv is not None:
            obj = sv.as_object() if hasattr(sv, "as_object") else sv
            if isinstance(obj, dict):
                sparse_part = {KEYWORD_VECTOR_NAME: obj}

        await self.client.upsert(
            collection_name=self.collection_name,
            points=[
                rest.PointStruct(
                    id=point_id,
                    vector={DEFAULT_VECTOR_NAME: entity.airweave_system_metadata.vectors[0]}
                    | sparse_part,
                    payload=data_object,
                )
            ],
            wait=True,
        )

    async def bulk_insert(self, entities: list[ChunkEntity]) -> None:
        """Bulk insert entities into Qdrant."""
        if not entities:
            return

        await self.ensure_client_readiness()

        point_structs = []
        for entity in entities:
            entity_data = entity.to_storage_dict()

            if not entity.airweave_system_metadata:
                raise ValueError(f"Entity {entity.entity_id} has no system metadata")
            if not entity.airweave_system_metadata.vectors:
                raise ValueError(f"Entity {entity.entity_id} has no vector in system metadata")

            # Remove vectors from payload
            if "airweave_system_metadata" in entity_data and isinstance(
                entity_data["airweave_system_metadata"], dict
            ):
                entity_data["airweave_system_metadata"].pop("vectors", None)

            # ✅ VALID Qdrant point id (UUID)
            point_id = self._make_point_uuid(
                entity.airweave_system_metadata.db_entity_id, entity.entity_id
            )

            sv = (
                entity.airweave_system_metadata.vectors[1]
                if entity.airweave_system_metadata.vectors
                else None
            )
            sparse_part = {}
            if sv is not None:
                obj = sv.as_object() if hasattr(sv, "as_object") else sv
                if isinstance(obj, dict):
                    sparse_part = {KEYWORD_VECTOR_NAME: obj}

            point_structs.append(
                rest.PointStruct(
                    id=point_id,
                    vector={DEFAULT_VECTOR_NAME: entity.airweave_system_metadata.vectors[0]}
                    | sparse_part,
                    payload=entity_data,
                )
            )

        if not point_structs:
            self.logger.warning("No valid entities to insert")
            return

        operation_response = await self.client.upsert(
            collection_name=self.collection_name,
            points=point_structs,
            wait=True,
        )

        if hasattr(operation_response, "errors") and operation_response.errors:
            raise Exception(f"Errors during bulk insert: {operation_response.errors}")

    async def delete(self, db_entity_id: UUID) -> None:
        """Delete all points belonging to a DB entity id (parent)."""
        await self.ensure_client_readiness()

        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest.FilterSelector(
                filter=rest.Filter(
                    must=[
                        rest.FieldCondition(
                            key="airweave_system_metadata.db_entity_id",
                            match=rest.MatchValue(value=str(db_entity_id)),
                        )
                    ]
                )
            ),
            wait=True,
        )

    async def delete_by_sync_id(self, sync_id: UUID) -> None:
        """Delete entities from the destination by sync ID."""
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
            wait=True,
        )

    async def bulk_delete(self, entity_ids: list[str], sync_id: UUID) -> None:
        """Bulk delete entities from Qdrant within a sync by child entity_ids."""
        if not entity_ids:
            return

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
            wait=True,
        )

    async def bulk_delete_by_parent_id(self, parent_id: str, sync_id: UUID) -> None:
        """Bulk delete entities from Qdrant by parent entity ID and sync ID."""
        if not parent_id:
            return

        await self.ensure_client_readiness()

        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=rest.FilterSelector(
                filter=rest.Filter(
                    must=[
                        rest.FieldCondition(
                            key="parent_entity_id", match=rest.MatchValue(value=str(parent_id))
                        ),
                        rest.FieldCondition(
                            key="airweave_system_metadata.sync_id",
                            match=rest.MatchValue(value=str(sync_id)),
                        ),
                    ]
                )
            ),
            wait=True,
        )

    async def bulk_delete_by_parent_ids(self, parent_ids: list[str], sync_id: UUID) -> None:
        """Optimized bulk delete for multiple parent IDs within a sync."""
        if not parent_ids:
            return

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
                        rest.FieldCondition(
                            key="parent_entity_id",
                            match=rest.MatchAny(any=[str(pid) for pid in parent_ids]),
                        ),
                    ]
                )
            ),
            wait=True,
        )

    def _prepare_index_search_request(
        self,
        params: dict,
        decay_config: Optional[DecayConfig] = None,
    ) -> dict:
        """Prepare a query request for Qdrant."""
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

        weight = getattr(decay_config, "weight", 1.0) if decay_config else 1.0

        if weight <= 0.0:
            weighted_formula = "$score"
        elif weight >= 1.0:
            weighted_formula = decay_expression
        else:
            decay_factor = rest.SumExpression(
                sum=[
                    1.0 - weight,
                    rest.MultExpression(mult=[weight, decay_expression]),
                ]
            )
            weighted_formula = rest.MultExpression(mult=["$score", decay_factor])

        try:
            self.logger.debug(
                f"[Qdrant] Decay formula applied: using={params.get('using')}, "
                f"weight={weight}, field={getattr(decay_config, 'datetime_field', None)}"
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
        sparse_vector: dict | None,
        search_method: Literal["hybrid", "neural", "keyword"],
        decay_config: Optional[DecayConfig] = None,
    ) -> rest.QueryRequest:
        """Prepare a query request for Qdrant."""
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
                "query": rest.SparseVector(**sparse_vector),
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

            prefetch_limit = 10000
            if decay_config is not None:
                try:
                    weight = max(0.0, min(1.0, float(getattr(decay_config, "weight", 0.0) or 0.0)))
                    if weight > 0.3:
                        prefetch_limit = int(10000 * (1 + weight))
                except Exception:
                    pass

            prefetch_params = [
                {"query": query_vector, "using": DEFAULT_VECTOR_NAME, "limit": prefetch_limit},
                {
                    "query": rest.SparseVector(**sparse_vector),
                    "using": KEYWORD_VECTOR_NAME,
                    "limit": prefetch_limit,
                },
            ]

            prefetches = [rest.Prefetch(**params) for params in prefetch_params]

            if decay_config is None or decay_config.weight <= 0.0:
                query_request_params = {
                    "prefetch": prefetches,
                    "query": rest.FusionQuery(fusion=rest.Fusion.RRF),
                }
            else:
                rrf_prefetch = rest.Prefetch(
                    prefetch=prefetches,
                    query=rest.FusionQuery(fusion=rest.Fusion.RRF),
                    limit=prefetch_limit,
                )
                decay_params = self._prepare_index_search_request(
                    params={}, decay_config=decay_config
                )
                query_request_params = {"prefetch": [rrf_prefetch], "query": decay_params["query"]}

        return rest.QueryRequest(**query_request_params)

    def _format_bulk_search_results(
        self, batch_results: list, with_payload: bool
    ) -> list[list[dict]]:
        """Format batch search results into standard format."""
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
        sparse_vector: dict | None = None,
        search_method: Literal["hybrid", "neural", "keyword"] = "hybrid",
        offset: int = 0,
    ) -> list[dict]:
        """Search for entities in the destination."""
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

    async def _build_query_requests(
        self,
        query_vectors: list[list[float]],
        limit: int,
        score_threshold: float | None,
        with_payload: bool,
        filter_conditions: list[dict] | None,
        sparse_vectors: list[dict] | None,
        search_method: Literal["hybrid", "neural", "keyword"],
        decay_config: Optional[DecayConfig],
        offset: Optional[int],
    ) -> list[rest.QueryRequest]:
        """Build a list of Qdrant query requests."""
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

            if filter_conditions and i < len(filter_conditions) and filter_conditions[i]:
                request.filter = rest.Filter.model_validate(filter_conditions[i])
            if offset and offset > 0:
                request.offset = offset
            if score_threshold is not None:
                request.score_threshold = score_threshold

            request.with_payload = with_payload
            query_requests.append(request)
        return query_requests

    async def bulk_search(
        self,
        query_vectors: list[list[float]],
        limit: int = 10,
        score_threshold: float | None = None,
        with_payload: bool = True,
        filter_conditions: list[dict] | None = None,
        sparse_vectors: list[dict] | None = None,
        search_method: Literal["hybrid", "neural", "keyword"] = "hybrid",
        decay_config: Optional[DecayConfig] = None,
        offset: Optional[int] = None,
    ) -> list[dict]:
        """Perform batch search for multiple query vectors in a single request."""
        await self.ensure_client_readiness()
        if not query_vectors:
            return []

        # Fallback to neural search if keyword index doesn't exist
        if search_method != "neural":
            vector_config_names = await self.get_vector_config_names()
            if KEYWORD_VECTOR_NAME not in vector_config_names:
                self.logger.warning(
                    (
                        f"'{KEYWORD_VECTOR_NAME}' index not found in collection ",
                        "'{self.collection_name}'. Falling back to neural search.",
                    )
                )
                search_method = "neural"

        self.logger.info(
            f"[Qdrant] Executing {search_method.upper()} search: "
            f"queries={len(query_vectors)}, limit={limit}, "
            f"decay_enabled={decay_config is not None}"
        )

        try:
            query_requests = await self._build_query_requests(
                query_vectors,
                limit,
                score_threshold,
                with_payload,
                filter_conditions,
                sparse_vectors,
                search_method,
                decay_config,
                offset,
            )

            batch_results = await self.client.query_batch_points(
                collection_name=self.collection_name, requests=query_requests
            )
            formatted_results = self._format_bulk_search_results(batch_results, with_payload)

            flattened_results = [item for sublist in formatted_results for item in sublist]

            if flattened_results:
                scores = [r.get("score", 0) for r in flattened_results if isinstance(r, dict)]
                if scores:
                    self.logger.debug(
                        (
                            f"[Qdrant] Result scores: count={len(scores)}, "
                            f"avg={sum(scores) / len(scores):.3f}, "
                            f"max={max(scores):.3f}, min={min(scores):.3f}"
                        )
                    )
            return flattened_results
        except Exception as e:
            self.logger.error(f"Error performing batch search with Qdrant: {e}")
            raise

    async def has_keyword_index(self) -> bool:
        """Check if the destination has a keyword index."""
        vector_config_names = await self.get_vector_config_names()
        return KEYWORD_VECTOR_NAME in vector_config_names

    async def get_vector_config_names(self) -> list[str]:
        """Get the names of all vector configurations (both dense and sparse) for the collection."""
        await self.ensure_client_readiness()

        try:
            collection_info = await self.client.get_collection(collection_name=self.collection_name)

            vector_config_names = []

            if collection_info.config.params.vectors:
                if isinstance(collection_info.config.params.vectors, dict):
                    vector_config_names.extend(collection_info.config.params.vectors.keys())
                else:
                    vector_config_names.append(DEFAULT_VECTOR_NAME)

            if collection_info.config.params.sparse_vectors:
                vector_config_names.extend(collection_info.config.params.sparse_vectors.keys())

            return vector_config_names

        except Exception as e:
            self.logger.error(
                f"Error getting vector configurations from collection {self.collection_name}: {e}"
            )
            raise
