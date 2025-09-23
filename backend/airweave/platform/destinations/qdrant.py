"""Qdrant destination implementation (compat with old sparse querying + batching).

- Keeps the *old* query semantics for sparse vectors (expects fastembed SparseEmbedding objects),
  including RRF fusion + optional recency decay.
- Accepts either fastembed sparse objects (with `.as_object()`) OR a raw dict shaped like
  {"indices": [...], "values": [...]} for maximum compatibility.
- Preserves the *improved* per-chunk deterministic UUIDv5 point IDs to avoid overwrites.
"""

from __future__ import annotations

import uuid
from typing import Literal, Optional
from uuid import UUID

# Prefer SparseTextEmbedding (newer fastembed), fallback to SparseEmbedding (older)
try:
    from fastembed import SparseTextEmbedding as SparseEmbedding  # type: ignore
except Exception:  # pragma: no cover
    try:
        from fastembed import SparseEmbedding  # type: ignore
    except Exception:  # pragma: no cover

        class SparseEmbedding:  # type: ignore
            """Fallback placeholder for type checking when fastembed isn't present."""

            pass


from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as rest
from qdrant_client.local.local_collection import DEFAULT_VECTOR_NAME

from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.platform.configs.auth import QdrantAuthConfig
from airweave.platform.decorators import destination
from airweave.platform.destinations._base import VectorDBDestination
from airweave.platform.entities._base import ChunkEntity
from airweave.search.decay import DecayConfig

KEYWORD_VECTOR_NAME = "bm25"


@destination("Qdrant", "qdrant", config_class=QdrantAuthConfig, supports_vector=True)
class QdrantDestination(VectorDBDestination):
    """Qdrant destination with legacy-compatible sparse querying + batch search."""

    def __init__(self):
        """Initialize defaults and placeholders for connection and collection state."""
        super().__init__()
        self.collection_name: str | None = None
        self.collection_id: UUID | None = None
        self.url: str | None = None
        self.api_key: str | None = None
        self.client: AsyncQdrantClient | None = None
        self.vector_size: int = 384  # Default dense vector size

    # ----------------------------------------------------------------------------------
    # Lifecycle / connection
    # ----------------------------------------------------------------------------------
    @classmethod
    async def create(
        cls, collection_id: UUID, logger: Optional[ContextualLogger] = None
    ) -> "QdrantDestination":
        """Create and return a connected destination for the given collection."""
        instance = cls()
        instance.set_logger(logger or default_logger)
        instance.collection_id = collection_id
        instance.collection_name = str(collection_id)

        credentials = await cls.get_credentials()
        if credentials:
            instance.url = credentials.url
            instance.api_key = credentials.api_key

        await instance.connect_to_qdrant()
        return instance

    @classmethod
    async def get_credentials(cls) -> QdrantAuthConfig | None:
        """Optionally provide credentials (override in your deployment)."""
        # TODO: hook to your creds provider
        return None

    async def connect_to_qdrant(self) -> None:
        """Initialize the AsyncQdrantClient and verify connectivity."""
        if self.client is not None:
            return
        try:
            location = self.url or settings.qdrant_url

            # Reverted to HTTP-only; broadest compatibility with qdrant-client versions.
            self.client = AsyncQdrantClient(
                url=location,
                api_key=self.api_key,
                timeout=120.0,  # float timeout (seconds) for connect/read/write
                prefer_grpc=False,  # revert: some setups don't expose gRPC
            )

            # Ping
            await self.client.get_collections()
            self.logger.debug("Successfully connected to Qdrant service.")
        except Exception as e:
            self.logger.error(f"Error connecting to Qdrant at {location}: {e}")
            self.client = None
            msg = str(e).lower()
            if "connection refused" in msg:
                raise ConnectionError(
                    f"Qdrant service is not running or refusing connections at {location}"
                ) from e
            if "timeout" in msg:
                raise ConnectionError(f"Connection to Qdrant timed out at {location}") from e
            if "authentication" in msg or "unauthorized" in msg:
                raise ConnectionError(f"Authentication failed for Qdrant at {location}") from e
            raise ConnectionError(f"Failed to connect to Qdrant at {location}: {str(e)}") from e

    async def ensure_client_readiness(self) -> None:
        """Ensure a connected client exists or raise a clear error."""
        if self.client is None:
            await self.connect_to_qdrant()
        if self.client is None:
            raise ConnectionError(
                "Failed to establish connection to Qdrant. Is the service accessible?"
            )

    async def close_connection(self) -> None:
        """Close the Qdrant client (drop the reference, let GC handle resources)."""
        if self.client:
            self.logger.debug("Closing Qdrant client connection...")
            self.client = None

    # ----------------------------------------------------------------------------------
    # Collection management
    # ----------------------------------------------------------------------------------
    async def collection_exists(self, collection_name: str) -> bool:
        """Check whether a collection exists by name."""
        await self.ensure_client_readiness()
        try:
            collections_response = await self.client.get_collections()
            return any(c.name == collection_name for c in collections_response.collections)
        except Exception as e:
            self.logger.error(f"Error checking if collection exists: {e}")
            raise

    async def setup_collection(self, *args, **kwargs) -> None:
        """Set up the collection (accepts both legacy and new signatures).

        Supported call styles:
          - setup_collection(vector_size)
          - setup_collection(collection_id, vector_size)
          - setup_collection(vector_size=..., collection_id=...)
        """
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
                "Call create(collection_id, ...) before setup_collection()."
            )

        try:
            if await self.collection_exists(self.collection_name):
                self.logger.debug(f"Collection {self.collection_name} already exists.")
                return

            self.logger.info(f"Creating collection {self.collection_name}...")
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    # DEFAULT_VECTOR_NAME is "" (empty string) in qdrant-client local
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
                optimizers_config=rest.OptimizersConfigDiff(indexing_threshold=20000),
                on_disk_payload=True,
            )

            # Range indexes for recency/filters
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

    # ----------------------------------------------------------------------------------
    # ID helper (deterministic per-chunk IDs; avoids overwrites)
    # ----------------------------------------------------------------------------------
    @staticmethod
    def _make_point_uuid(db_entity_id: UUID | str, child_entity_id: str) -> str:
        """Create a deterministic UUIDv5 for a chunk based on its parent DB id and entity id."""
        ns = UUID(str(db_entity_id)) if not isinstance(db_entity_id, UUID) else db_entity_id
        return str(uuid.uuid5(ns, child_entity_id))

    # ----------------------------------------------------------------------------------
    # Insert / Upsert
    # ----------------------------------------------------------------------------------
    async def insert(self, entity: ChunkEntity) -> None:
        """Upsert a single chunk entity into Qdrant."""
        await self.ensure_client_readiness()

        data_object = entity.to_storage_dict()

        # Sanity checks
        if not entity.airweave_system_metadata or not entity.airweave_system_metadata.vectors:
            raise ValueError(f"Entity {entity.entity_id} has no vector in system metadata")
        if not entity.airweave_system_metadata.db_entity_id:
            raise ValueError(f"Entity {entity.entity_id} has no db_entity_id in system metadata")

        # Remove vectors from payload (store them only in vector fields)
        if "airweave_system_metadata" in data_object and isinstance(
            data_object["airweave_system_metadata"], dict
        ):
            data_object["airweave_system_metadata"].pop("vectors", None)

        # Deterministic per-chunk ID
        point_id = self._make_point_uuid(
            entity.airweave_system_metadata.db_entity_id, entity.entity_id
        )

        # Optional sparse (accepts fastembed object or dict)
        sv = entity.airweave_system_metadata.vectors[1]
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

    # --------- NEW: helpers to keep bulk_insert simple (fixes C901) -------------------
    def _build_point_struct(self, entity: ChunkEntity) -> rest.PointStruct:
        """Convert a ChunkEntity to a Qdrant PointStruct."""
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

        point_id = self._make_point_uuid(
            entity.airweave_system_metadata.db_entity_id, entity.entity_id
        )

        sv = entity.airweave_system_metadata.vectors[1]
        sparse_part: dict = {}
        if sv is not None:
            obj = sv.as_object() if hasattr(sv, "as_object") else sv
            if isinstance(obj, dict):
                sparse_part = {KEYWORD_VECTOR_NAME: obj}

        return rest.PointStruct(
            id=point_id,
            vector={DEFAULT_VECTOR_NAME: entity.airweave_system_metadata.vectors[0]} | sparse_part,
            payload=entity_data,
        )

    async def _upsert_points_with_fallback(
        self, points: list[rest.PointStruct], *, min_batch: int = 50
    ) -> None:
        """Try full batch; on write-timeout/transport error, split in half and retry."""
        # Build exception tuples safely without C408 (use literals)
        rhex: tuple[type[BaseException], ...] = ()
        try:
            from qdrant_client.http.exceptions import ResponseHandlingException  # type: ignore

            rhex = (ResponseHandlingException,)  # type: ignore[assignment]
        except Exception:  # pragma: no cover
            rhex = ()

        write_timeout_errors: tuple[type[BaseException], ...] = ()
        try:
            import httpcore  # type: ignore
            import httpx

            write_timeout_errors = (httpx.WriteTimeout, httpcore.WriteTimeout)
        except Exception:  # pragma: no cover
            write_timeout_errors = ()

        try:
            op = await self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )
            if hasattr(op, "errors") and op.errors:
                raise Exception(f"Errors during bulk insert: {op.errors}")
        except (*write_timeout_errors, *rhex) as e:  # type: ignore[misc]
            n = len(points)
            if n <= 1 or n <= min_batch:
                self.logger.error(
                    f"[Qdrant] Upsert failed on batch of {n} (min_batch={min_batch}): {e}"
                )
                raise
            mid = n // 2
            left, right = points[:mid], points[mid:]
            self.logger.warning(
                f"[Qdrant] Write timed out for {n} points; splitting into "
                f"{len(left)} + {len(right)} and retrying..."
            )
            await self._upsert_points_with_fallback(left, min_batch=min_batch)
            await self._upsert_points_with_fallback(right, min_batch=min_batch)

    # ----------------------------------------------------------------------------------
    async def bulk_insert(self, entities: list[ChunkEntity]) -> None:
        """Upsert multiple chunk entities with fallback halving on write timeouts."""
        if not entities:
            return

        await self.ensure_client_readiness()

        point_structs = [self._build_point_struct(e) for e in entities]

        if not point_structs:
            self.logger.warning("No valid entities to insert")
            return

        # Try once with the whole payload; fall back to halving on failure
        await self._upsert_points_with_fallback(point_structs, min_batch=50)

    # ----------------------------------------------------------------------------------
    # Deletes (by parent/sync/etc.)
    # ----------------------------------------------------------------------------------
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
        """Delete all points that have the provided sync job id."""
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
        """Delete specific entity ids that belong to a particular sync job."""
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

    async def bulk_delete_by_parent_id(self, parent_id: str, sync_id: UUID | str) -> None:
        """Delete all points for a given parent (db entity) id and sync id."""
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
        """Delete all points whose parent id is in the provided list and match sync id."""
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

    # ----------------------------------------------------------------------------------
    # Query building (legacy-compatible sparse semantics)
    # ----------------------------------------------------------------------------------
    def _prepare_index_search_request(
        self,
        params: dict,
        decay_config: Optional[DecayConfig] = None,
    ) -> dict:
        """Wrap an index search with optional decay formula (same semantics as old code)."""
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
            # score * (1 - weight + weight * decay)
            decay_factor = rest.SumExpression(
                sum=[1.0 - weight, rest.MultExpression(mult=[weight, decay_expression])]
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
        sparse_vector: SparseEmbedding | dict | None,
        search_method: Literal["hybrid", "neural", "keyword"],
        decay_config: Optional[DecayConfig] = None,
    ) -> rest.QueryRequest:
        """Create a single QueryRequest consistent with the old method."""
        query_request_params: dict = {}

        if search_method == "neural":
            neural_params = {
                "query": query_vector,
                "using": DEFAULT_VECTOR_NAME,
                "limit": limit,
            }
            query_request_params = self._prepare_index_search_request(neural_params, decay_config)

        if search_method == "keyword":
            if not sparse_vector:
                raise ValueError("Keyword search requires sparse vector")
            obj = (
                sparse_vector.as_object() if hasattr(sparse_vector, "as_object") else sparse_vector
            )
            keyword_params = {
                "query": rest.SparseVector(**obj),
                "using": KEYWORD_VECTOR_NAME,
                "limit": limit,
            }
            query_request_params = self._prepare_index_search_request(keyword_params, decay_config)

        if search_method == "hybrid":
            if not sparse_vector:
                raise ValueError("Hybrid search requires sparse vector")
            obj = (
                sparse_vector.as_object() if hasattr(sparse_vector, "as_object") else sparse_vector
            )

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
                    "query": rest.SparseVector(**obj),
                    "using": KEYWORD_VECTOR_NAME,
                    "limit": prefetch_limit,
                },
            ]
            prefetches = [rest.Prefetch(**p) for p in prefetch_params]

            if decay_config is None or getattr(decay_config, "weight", 0.0) <= 0.0:
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

    def _validate_bulk_search_inputs(
        self,
        query_vectors: list[list[float]],
        filter_conditions: list[dict] | None,
        sparse_vectors: list[SparseEmbedding] | list[dict] | None,
    ) -> None:
        """Validate lengths of per-query inputs for bulk search."""
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
        sparse_vectors: list[SparseEmbedding] | list[dict] | None,
        search_method: Literal["hybrid", "neural", "keyword"],
        decay_config: Optional[DecayConfig],
        offset: Optional[int],
    ) -> list[rest.QueryRequest]:
        """Create per-query request objects used by `bulk_search`."""
        requests: list[rest.QueryRequest] = []
        for i, qv in enumerate(query_vectors):
            sv = sparse_vectors[i] if sparse_vectors else None
            req = await self._prepare_query_request(
                query_vector=qv,
                limit=limit,
                sparse_vector=sv,
                search_method=search_method,
                decay_config=decay_config,
            )
            if filter_conditions and filter_conditions[i]:
                req.filter = rest.Filter.model_validate(filter_conditions[i])
            if offset and offset > 0:
                req.offset = offset
            if score_threshold is not None:
                req.score_threshold = score_threshold
            req.with_payload = with_payload
            requests.append(req)
        return requests

    def _format_bulk_search_results(
        self, batch_results: list, with_payload: bool
    ) -> list[list[dict]]:
        """Convert client batch results to a simple nested list of dicts."""
        all_results: list[list[dict]] = []
        for search_results in batch_results:
            results = []
            for result in search_results.points:
                entry = {"id": result.id, "score": result.score}
                if with_payload:
                    entry["payload"] = result.payload
                results.append(entry)
            all_results.append(results)
        return all_results

    # ----------------------------------------------------------------------------------
    # Public search API (legacy-compatible signatures)
    # ----------------------------------------------------------------------------------
    async def search(
        self,
        query_vector: list[float],
        limit: int = 100,
        score_threshold: float | None = None,
        with_payload: bool = True,
        filter: dict | None = None,
        decay_config: Optional[DecayConfig] = None,
        sparse_vector: SparseEmbedding | dict | None = None,
        search_method: Literal["hybrid", "neural", "keyword"] = "hybrid",
        offset: int = 0,
    ) -> list[dict]:
        """Search a single query vector; thin wrapper over `bulk_search`."""
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
        limit: int = 100,
        score_threshold: float | None = None,
        with_payload: bool = True,
        filter_conditions: list[dict] | None = None,
        sparse_vectors: list[SparseEmbedding] | list[dict] | None = None,
        search_method: Literal["hybrid", "neural", "keyword"] = "hybrid",
        decay_config: Optional[DecayConfig] = None,
        offset: Optional[int] = None,
    ) -> list[dict]:
        """Search multiple queries at once with neural/keyword/hybrid and optional decay."""
        await self.ensure_client_readiness()
        if not query_vectors:
            return []

        self._validate_bulk_search_inputs(query_vectors, filter_conditions, sparse_vectors)

        if search_method != "neural":
            vector_config_names = await self.get_vector_config_names()
            if KEYWORD_VECTOR_NAME not in vector_config_names:
                self.logger.warning(
                    f"{KEYWORD_VECTOR_NAME} index could not be found in "
                    f"collection {self.collection_name}. Using neural search instead."
                )
                search_method = "neural"

        weight = getattr(decay_config, "weight", None) if decay_config else None
        self.logger.info(
            f"[Qdrant] Executing {search_method.upper()} search: "
            f"queries={len(query_vectors)}, limit={limit}, "
            f"has_sparse={sparse_vectors is not None}, "
            f"decay_enabled={decay_config is not None}, "
            f"decay_weight={weight}"
        )

        if decay_config:
            decay_weight = getattr(decay_config, "weight", 0)
            decay_field = decay_config.datetime_field
            decay_scale = getattr(decay_config, "scale_value", None)
            self.logger.debug(
                "[Qdrant] Decay strategy: weight=%.1f, field=%s, scale=%ss",
                decay_weight,
                decay_field,
                decay_scale,
            )

        try:
            requests = await self._prepare_bulk_search_requests(
                query_vectors=query_vectors,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=with_payload,
                filter_conditions=filter_conditions or [None] * len(query_vectors),
                sparse_vectors=sparse_vectors,
                search_method=search_method,
                decay_config=decay_config,
                offset=offset,
            )

            batch_results = await self.client.query_batch_points(
                collection_name=self.collection_name, requests=requests
            )
            formatted = self._format_bulk_search_results(batch_results, with_payload)

            # Flatten to match previous public API behavior
            flattened: list[dict] = [item for group in formatted for item in group]

            if flattened:
                scores = [r.get("score", 0) for r in flattened if isinstance(r, dict)]
                if scores:
                    avg = sum(scores) / len(scores)
                    self.logger.debug(
                        "[Qdrant] Result scores with %s %s: count=%d, avg=%.3f, max=%.3f, min=%.3f",
                        search_method,
                        "(with recency)" if decay_config else "(no recency)",
                        len(scores),
                        avg,
                        max(scores),
                        min(scores),
                    )
            return flattened

        except Exception as e:
            self.logger.error(f"Error performing batch search with Qdrant: {e}")
            raise

    # ----------------------------------------------------------------------------------
    # Introspection
    # ----------------------------------------------------------------------------------
    async def has_keyword_index(self) -> bool:
        """Return True if the BM25 (sparse) index exists for the collection."""
        names = await self.get_vector_config_names()
        return KEYWORD_VECTOR_NAME in names

    async def get_vector_config_names(self) -> list[str]:
        """Return all configured vector names (dense and sparse) for the collection."""
        await self.ensure_client_readiness()
        try:
            info = await self.client.get_collection(collection_name=self.collection_name)
            names: list[str] = []
            if info.config.params.vectors:
                if isinstance(info.config.params.vectors, dict):
                    names.extend(info.config.params.vectors.keys())
                else:
                    names.append(DEFAULT_VECTOR_NAME)
            if info.config.params.sparse_vectors:
                names.extend(info.config.params.sparse_vectors.keys())
            return names
        except Exception as e:
            self.logger.error(
                f"Error getting vector configurations from collection {self.collection_name}: {e}"
            )
            raise
