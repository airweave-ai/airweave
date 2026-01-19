"""Qdrant destination implementation (compat with old sparse querying + batching).

- Keeps the *old* query semantics for sparse vectors (expects fastembed SparseEmbedding objects),
  including RRF fusion + optional recency decay.
- Accepts either fastembed sparse objects (with `.as_object()`) OR a raw dict shaped like
  {"indices": [...], "values": [...]} for maximum compatibility.
- Preserves the *improved* per-chunk deterministic UUIDv5 point IDs to avoid overwrites.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel

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
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
from qdrant_client.local.local_collection import DEFAULT_VECTOR_NAME

from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.platform.configs.auth import QdrantAuthConfig
from airweave.platform.decorators import destination
from airweave.platform.destinations._base import VectorDBDestination
from airweave.platform.destinations.collection_strategy import (
    get_default_vector_size,
    get_physical_collection_name,
)
from airweave.platform.entities._base import BaseEntity
from airweave.schemas.search import AirweaveTemporalConfig, RetrievalStrategy
from airweave.schemas.search_result import (
    AccessControlResult,
    AirweaveSearchResult,
    BreadcrumbResult,
    SystemMetadataResult,
)


class DecayConfig(BaseModel):
    """Qdrant-specific configuration for time-based decay in queries.

    This is the native format that Qdrant's query API expects for temporal
    relevance scoring. Created by translating AirweaveTemporalConfig.
    """

    decay_type: str  # "linear", "exponential", "gaussian"
    datetime_field: str
    target_datetime: datetime
    scale_seconds: float
    midpoint: float
    weight: float

    def get_scale_seconds(self) -> float:
        """Get scale in seconds for decay calculation."""
        return self.scale_seconds


KEYWORD_VECTOR_NAME = "bm25"


@destination(
    "Qdrant",
    "qdrant",
    auth_config_class=QdrantAuthConfig,
    supports_vector=True,
    requires_client_embedding=True,
    supports_temporal_relevance=False,  # Disabled while Vespa support is pending
)
class QdrantDestination(VectorDBDestination):
    """Qdrant destination with multi-tenant support and legacy compatibility."""

    # Default write concurrency (simple, code-local tuning)
    DEFAULT_WRITE_CONCURRENCY: int = 16

    def __init__(self, soft_fail: bool = True):
        """Initialize defaults and placeholders for connection and collection state.

        Args:
            soft_fail: If True, errors won't fail the sync (default True - Qdrant is secondary)
        """
        super().__init__(soft_fail=soft_fail)
        # Logical identifiers (from SQL)
        self.collection_id: UUID | None = None
        self.organization_id: UUID | None = None

        # Physical collection mapping
        self.collection_name: str | None = None  # Physical collection name

        # Connection
        self.url: str | None = None
        self.api_key: str | None = None
        self.client: AsyncQdrantClient | None = None
        self.vector_size: int = 384  # Default dense vector size

        # Write concurrency control (caps concurrent writes per destination)
        self._write_limit = self._compute_write_concurrency()
        self._write_sem = asyncio.Semaphore(self._write_limit)

        # One-time collection readiness cache
        self._collection_ready: bool = False
        self._collection_ready_lock = asyncio.Lock()

    # ----------------------------------------------------------------------------------
    # Lifecycle / connection
    # ----------------------------------------------------------------------------------
    @classmethod
    async def create(
        cls,
        collection_id: UUID,
        organization_id: Optional[UUID] = None,
        vector_size: Optional[int] = None,
        credentials: Optional[QdrantAuthConfig] = None,
        config: Optional[dict] = None,
        logger: Optional[ContextualLogger] = None,
        soft_fail: bool = True,
    ) -> "QdrantDestination":
        """Create and return a connected destination (matches source pattern).

        Args:
            collection_id: SQL collection UUID
            organization_id: Organization UUID
            vector_size: Vector dimensions - auto-detected if not provided:
                         - 1536 if OpenAI API key is set (text-embedding-3-small)
                         - 384 otherwise (MiniLM-L6-v2)
            credentials: Optional QdrantAuthConfig with url and api_key (None for native)
            config: Unused (kept for interface consistency with sources)
            logger: Logger instance
            soft_fail: If True, errors won't fail the sync (default True - Qdrant is secondary)

        Returns:
            Configured QdrantDestination instance with multi-tenant shared collection

        Note:
            Tenant isolation is achieved via airweave_collection_id filtering in Qdrant.
            Each collection belongs to exactly one organization, so collection_id is sufficient.
        """
        instance = cls(soft_fail=soft_fail)
        instance.set_logger(logger or default_logger)
        instance.collection_id = collection_id
        instance.organization_id = organization_id
        instance.vector_size = vector_size if vector_size is not None else get_default_vector_size()

        # Map to physical shared collection
        instance.collection_name = get_physical_collection_name(vector_size=instance.vector_size)
        instance.logger.info(f"Mapped collection {collection_id} → {instance.collection_name}")

        # Extract from credentials (contains both auth and config)
        if credentials:
            instance.url = credentials.url
            instance.api_key = credentials.api_key
        else:
            # Fall back to settings for native connection
            instance.url = None  # Will use settings.qdrant_url in connect_to_qdrant()
            instance.api_key = None

        # Reconfigure concurrency after we know the true vector size
        instance._write_limit = instance._compute_write_concurrency()
        instance._write_sem = asyncio.Semaphore(instance._write_limit)
        instance.logger.info(
            "[Qdrant] Write concurrency configured to %s/%s (vector_size=%s)",
            instance._write_sem._value,
            instance._write_limit,
            instance.vector_size,
        )

        await instance.connect_to_qdrant()
        return instance

    async def ensure_collection_ready(self) -> None:
        """Ensure the physical collection exists exactly once per instance.

        Avoids repeated get_collections() calls under high write load.
        """
        await self.ensure_client_readiness()
        if self._collection_ready:
            return
        async with self._collection_ready_lock:
            if self._collection_ready:
                return
            exists = False
            try:
                if self.collection_name:
                    exists = await self.collection_exists(self.collection_name)
            except Exception:
                exists = False
            if not exists:
                self.logger.error(
                    f"[Qdrant] Collection {self.collection_name} does NOT exist! "
                    f"collection_id={self.collection_id}. Creating it now..."
                )
                await self.setup_collection(self.vector_size)
            self._collection_ready = True

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

    def _compute_write_concurrency(self) -> int:
        """Derive write concurrency based on embedding dimensionality."""
        concurrency = self.DEFAULT_WRITE_CONCURRENCY

        if self.vector_size >= 3000:
            concurrency = max(2, concurrency // 4)
        elif self.vector_size >= 1024:
            concurrency = max(4, concurrency // 2)

        return concurrency

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

    async def setup_collection(self, vector_size: int | None = None) -> None:
        """Set up physical Qdrant collection with multi-tenant support.

        Implements Qdrant's multi-tenancy recommendations:
        - payload_m=16, m=0 for per-tenant HNSW indexes
        - Tenant keyword index with is_tenant=true for co-location

        See: https://qdrant.tech/documentation/guides/multiple-partitions/

        Args:
            vector_size: Vector dimensions (optional, uses instance value if not provided)
        """
        if vector_size:
            self.vector_size = vector_size
            self._write_limit = self._compute_write_concurrency()
            self._write_sem = asyncio.Semaphore(self._write_limit)

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

            self.logger.info(f"Creating physical collection {self.collection_name}...")

            # Per-tenant HNSW as per Qdrant docs
            # https://qdrant.tech/documentation/guides/multiple-partitions/#calibrate-performance
            hnsw_config = rest.HnswConfigDiff(
                payload_m=16,  # Build per-tenant HNSW
                m=0,  # Disable global HNSW
                ef_construct=100,
            )

            # Quantization config for optimal performance with 100GB RAM
            # int8 scalar quantization with always_ram keeps both quantized and original in memory
            # Fast initial search (int8) + accurate rescoring (float32) with no disk I/O
            quantization_config = rest.ScalarQuantization(
                scalar=rest.ScalarQuantizationConfig(
                    type=rest.ScalarType.INT8,
                    quantile=0.99,
                    always_ram=True,
                )
            )

            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    DEFAULT_VECTOR_NAME: rest.VectorParams(
                        size=self.vector_size,
                        distance=rest.Distance.COSINE,
                        on_disk=True,  # Store vectors on disk, load for rescoring on-demand
                    ),
                },
                sparse_vectors_config={
                    KEYWORD_VECTOR_NAME: rest.SparseVectorParams(
                        modifier=rest.Modifier.IDF,
                    )
                },
                hnsw_config=hnsw_config,
                optimizers_config=rest.OptimizersConfigDiff(
                    indexing_threshold=20000,
                    max_segment_size=200000,  # Smaller segments for better filtering
                ),
                quantization_config=quantization_config,
                on_disk_payload=True,
            )

            # Tenant index for co-location and performance
            # https://qdrant.tech/documentation/guides/multiple-partitions/#calibrate-performance
            self.logger.info("Creating tenant index on collection_id")
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="airweave_collection_id",
                field_schema=rest.KeywordIndexParams(
                    type=rest.PayloadSchemaType.KEYWORD,
                    is_tenant=True,  # Enables co-location optimization
                ),
            )

            # Indexes for delete operations (critical for WAL performance)
            # Without these, deletes become full collection scans during recovery
            self.logger.info("Creating sync_id index for delete operations")
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="airweave_system_metadata.sync_id",
                field_schema=rest.PayloadSchemaType.KEYWORD,
            )

            self.logger.info("Creating db_entity_id index for delete operations")
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="airweave_system_metadata.db_entity_id",
                field_schema=rest.PayloadSchemaType.KEYWORD,
            )

            self.logger.info("Creating entity_id index for bulk delete operations")
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="entity_id",
                field_schema=rest.PayloadSchemaType.KEYWORD,
            )

            self.logger.info("Creating original_entity_id index for parent-based deletes")
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="airweave_system_metadata.original_entity_id",
                field_schema=rest.PayloadSchemaType.KEYWORD,
            )

            # Timestamp indexes for recency boosting
            self.logger.debug(
                f"Creating range indexes for timestamp fields in {self.collection_name}..."
            )
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="updated_at",
                field_schema=rest.PayloadSchemaType.DATETIME,
            )
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="created_at",
                field_schema=rest.PayloadSchemaType.DATETIME,
            )

            self.logger.info(f"✓ Collection {self.collection_name} created successfully")

        except Exception as e:
            if "already exists" not in str(e):
                raise

    # ----------------------------------------------------------------------------------
    # ID helper (deterministic per-chunk IDs; avoids overwrites)
    # ----------------------------------------------------------------------------------
    @staticmethod
    def _make_point_uuid(sync_id: UUID | str, chunk_entity_id: str) -> str:
        """Create a deterministic UUIDv5 for a chunk based on sync_id and entity_id."""
        ns = UUID(str(sync_id)) if not isinstance(sync_id, UUID) else sync_id
        return str(uuid.uuid5(ns, chunk_entity_id))

    # ----------------------------------------------------------------------------------
    # Insert / Upsert
    # ----------------------------------------------------------------------------------
    def _build_point_struct(self, entity: BaseEntity) -> rest.PointStruct:
        """Convert a BaseEntity to a Qdrant PointStruct with tenant metadata."""
        # Validate required fields first
        if not entity.airweave_system_metadata:
            raise ValueError(f"Entity {entity.entity_id} has no system metadata")
        if entity.airweave_system_metadata.dense_embedding is None:
            raise ValueError(f"Entity {entity.entity_id} has no dense_embedding in system metadata")
        if not entity.airweave_system_metadata.sync_id:
            raise ValueError(f"Entity {entity.entity_id} has no sync_id in system metadata")

        # Get entity data as dict, excluding embeddings to avoid numpy serialization issues
        entity_data = entity.model_dump(
            mode="json",
            exclude_none=True,
            exclude={"airweave_system_metadata": {"dense_embedding", "sparse_embedding"}},
        )

        # CRITICAL: Remove explicit None values from timestamps (Pydantic may include them)
        # This prevents Qdrant decay formula errors on documents without valid timestamps
        if entity_data.get("updated_at") is None:
            entity_data.pop("updated_at", None)
        if entity_data.get("created_at") is None:
            entity_data.pop("created_at", None)

        # CRITICAL: Normalize timestamps for temporal relevance
        # If updated_at is missing/null but created_at has a value, use created_at as fallback
        # This ensures temporal decay can work on documents that only have created_at
        if (
            "updated_at" not in entity_data or entity_data.get("updated_at") is None
        ) and entity_data.get("created_at") is not None:
            entity_data["updated_at"] = entity_data["created_at"]
            self.logger.debug(
                f"[Qdrant] Normalized timestamp: copied created_at → updated_at "
                f"for entity {entity.entity_id}"
            )

        # Add tenant metadata for filtering
        entity_data["airweave_collection_id"] = str(self.collection_id)

        point_id = self._make_point_uuid(entity.airweave_system_metadata.sync_id, entity.entity_id)

        # Build sparse vector part if present
        sparse_part: dict = {}
        sv = entity.airweave_system_metadata.sparse_embedding
        if sv is not None:
            obj = sv.as_object() if hasattr(sv, "as_object") else sv
            if isinstance(obj, dict):
                sparse_part = {KEYWORD_VECTOR_NAME: obj}

        return rest.PointStruct(
            id=point_id,
            vector={DEFAULT_VECTOR_NAME: entity.airweave_system_metadata.dense_embedding}
            | sparse_part,
            payload=entity_data,
        )

    def _max_points_per_batch(self) -> int:
        """Determine the maximum points to send in a single upsert request."""
        if self.vector_size >= 3000:
            return 40
        if self.vector_size >= 1024:
            return 60
        return 100

    async def _upsert_points_with_fallback(  # noqa: C901
        self, points: list[rest.PointStruct], *, min_batch: int = 50
    ) -> None:
        """Upsert points in batches to prevent timeouts and allow heartbeats.

        Proactively splits large batches to avoid blocking and timeouts.
        Falls back to smaller batches on errors.
        """
        # Import httpx timeout exceptions
        try:
            import httpcore
            import httpx

            timeout_errors = (
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpcore.ReadTimeout,
                httpcore.WriteTimeout,
            )
        except Exception:  # pragma: no cover
            timeout_errors = ()

        # Proactively batch large upserts to prevent timeouts and allow heartbeats
        MAX_BATCH_SIZE = self._max_points_per_batch()

        if len(points) > MAX_BATCH_SIZE:
            self.logger.debug(
                f"[Qdrant] Batching {len(points)} points into chunks of {MAX_BATCH_SIZE} "
                f"(vector_size={self.vector_size}) to prevent timeout and allow heartbeats"
            )
            for i in range(0, len(points), MAX_BATCH_SIZE):
                batch = points[i : i + MAX_BATCH_SIZE]
                await self._upsert_points_with_fallback(batch, min_batch=min_batch)
                # Yield control to event loop between batches (for heartbeats)
                await asyncio.sleep(0)
            return

        try:
            start_time = asyncio.get_event_loop().time()
            self.logger.debug(
                f"[Qdrant] Upserting {len(points)} points to collection={self.collection_name}, "
                f"collection_id={self.collection_id}, vector_size={self.vector_size}"
            )
            op = await self.client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )
            duration = asyncio.get_event_loop().time() - start_time

            if hasattr(op, "errors") and op.errors:
                raise Exception(f"Errors during bulk insert: {op.errors}")

            # SUCCESS LOGGING - Critical for diagnosing performance
            if duration > 10.0:
                self.logger.warning(
                    f"[Qdrant] ⚠️ Slow upsert: {len(points)} points took {duration:.2f}s "
                    f"(collection={self.collection_name}, vector_size={self.vector_size})"
                )
            else:
                self.logger.info(
                    f"[Qdrant] ✅ Upserted {len(points)} points in {duration:.2f}s "
                    f"(collection={self.collection_name})"
                )

        except UnexpectedResponse as e:
            # Qdrant returned an HTTP error (503, 429, etc.)
            n = len(points)

            # Extract ALL available error details from Qdrant response
            error_detail = None
            full_error_data = None
            try:
                error_data = e.structured()
                full_error_data = error_data  # Keep for detailed logging
                # Qdrant error format: {"status": {"error": "message"}} or {"status": "message"}
                if isinstance(error_data.get("status"), dict):
                    error_detail = error_data["status"].get("error")
                else:
                    error_detail = error_data.get("status") or error_data.get("message")
            except Exception:
                # Fallback to raw content if JSON parsing fails
                error_detail = e.content.decode("utf-8")[:500] if e.content else e.reason_phrase

            # Build comprehensive error context
            error_context = {
                "http_status": e.status_code,
                "reason_phrase": e.reason_phrase,
                "error_detail": error_detail,
                "collection_name": self.collection_name,
                "collection_id": str(self.collection_id),
                "vector_size": self.vector_size,
                "num_points": n,
                "min_batch": min_batch,
                "url": self.url or "native",
            }

            # Add full structured error if available
            if full_error_data:
                error_context["qdrant_response"] = full_error_data

            # Add request sample (first point payload keys)
            if points:
                try:
                    sample_payload_keys = list(points[0].payload.keys())[:10]
                    error_context["sample_payload_keys"] = sample_payload_keys
                except Exception:
                    pass

            error_summary = f"HTTP {e.status_code} {e.reason_phrase}" + (
                f": {error_detail}" if error_detail else ""
            )

            if n <= 1 or n <= min_batch:
                self.logger.error(
                    f"[Qdrant] 💥 FATAL rejection: Cannot split further "
                    f"- {n} points ≤ min_batch={min_batch}. "
                    f"Error: {error_summary}",
                    extra={"error_context": error_context},
                    exc_info=True,
                )
                # Log full error details on separate line for easier parsing
                self.logger.error(f"[Qdrant] Error context: {error_context}")
                raise

            mid = n // 2
            left, right = points[:mid], points[mid:]
            self.logger.warning(
                f"[Qdrant] ⚠️  Rejection for {n} points; "
                f"splitting into {len(left)} + {len(right)} and retrying... "
                f"({error_summary})",
                extra={"error_context": error_context},
            )
            await asyncio.sleep(0.2)
            await self._upsert_points_with_fallback(left, min_batch=min_batch)
            await asyncio.sleep(0.2)
            await self._upsert_points_with_fallback(right, min_batch=min_batch)

        except ResponseHandlingException as e:
            # Wrapper for underlying network/parsing errors
            n = len(points)
            source_error = e.source

            # Build comprehensive error context
            error_context = {
                "wrapper_exception": "ResponseHandlingException",
                "source_exception_type": type(source_error).__name__ if source_error else "None",
                "source_exception_message": str(source_error)
                if source_error
                else "No source error provided",
                "response_handling_exception_str": str(e) or "Empty ResponseHandlingException",
                "collection_name": self.collection_name,
                "collection_id": str(self.collection_id),
                "vector_size": self.vector_size,
                "num_points": n,
                "min_batch": min_batch,
                "url": self.url or "native",
            }

            # Extract any HTTP-related details from source error
            if source_error and hasattr(source_error, "status_code"):
                error_context["http_status"] = source_error.status_code
            if source_error and hasattr(source_error, "request"):
                try:
                    error_context["request_method"] = source_error.request.method
                    error_context["request_url"] = str(source_error.request.url)
                except Exception:
                    pass

            # Build error summary with fallback for missing source
            if source_error:
                error_summary = (
                    f"{type(source_error).__name__}: {source_error or '(empty error message)'}"
                )
            else:
                error_summary = (
                    f"ResponseHandlingException with no source error: {str(e) or '(empty)'}"
                )

            if n <= 1 or n <= min_batch:
                self.logger.error(
                    f"[Qdrant] 💥 FATAL error: Cannot split further "
                    f"- {n} points ≤ min_batch={min_batch}. "
                    f"Error: {error_summary}",
                    extra={"error_context": error_context},
                    exc_info=True,
                )
                # Log full error details on separate line for easier parsing
                self.logger.error(f"[Qdrant] Error context: {error_context}")
                raise

            mid = n // 2
            left, right = points[:mid], points[mid:]
            self.logger.warning(
                f"[Qdrant] ⚠️  Response handling error for {n} points; "
                f"splitting into {len(left)} + {len(right)} and retrying... "
                f"({error_summary})",
                extra={"error_context": error_context},
            )
            await asyncio.sleep(0.2)
            await self._upsert_points_with_fallback(left, min_batch=min_batch)
            await asyncio.sleep(0.2)
            await self._upsert_points_with_fallback(right, min_batch=min_batch)

        except timeout_errors as e:  # type: ignore[misc]
            # Network timeout (httpx/httpcore)
            n = len(points)

            # Build comprehensive timeout error context
            error_context = {
                "exception_type": type(e).__name__,
                "exception_message": str(e),
                "collection_name": self.collection_name,
                "collection_id": str(self.collection_id),
                "vector_size": self.vector_size,
                "num_points": n,
                "min_batch": min_batch,
                "url": self.url or "native",
                "client_timeout_setting": 120.0,  # From connect_to_qdrant
            }

            # Try to extract request details if available
            if hasattr(e, "request"):
                try:
                    error_context["request_method"] = e.request.method
                    error_context["request_url"] = str(e.request.url)
                except Exception:
                    pass

            # Estimate payload size
            try:
                import sys

                total_size_mb = sys.getsizeof(points) / (1024 * 1024)
                error_context["estimated_payload_size_mb"] = round(total_size_mb, 2)
            except Exception:
                pass

            error_summary = f"{type(e).__name__}: {e}"

            if n <= 1 or n <= min_batch:
                self.logger.error(
                    f"[Qdrant] 💥 FATAL timeout: Cannot split further "
                    f"- {n} points ≤ min_batch={min_batch}. "
                    f"Error: {error_summary}",
                    extra={"error_context": error_context},
                    exc_info=True,
                )
                # Log full error details on separate line for easier parsing
                self.logger.error(f"[Qdrant] Error context: {error_context}")
                raise

            mid = n // 2
            left, right = points[:mid], points[mid:]
            self.logger.warning(
                f"[Qdrant] ⚠️  Timeout for {n} points; "
                f"splitting into {len(left)} + {len(right)} and retrying... "
                f"({error_summary})",
                extra={"error_context": error_context},
            )
            await asyncio.sleep(0.2)
            await self._upsert_points_with_fallback(left, min_batch=min_batch)
            await asyncio.sleep(0.2)
            await self._upsert_points_with_fallback(right, min_batch=min_batch)

    # ----------------------------------------------------------------------------------
    async def bulk_insert(self, entities: list[BaseEntity]) -> None:
        """Upsert multiple chunk entities with fallback halving on write timeouts."""
        if not entities:
            return

        await self.ensure_client_readiness()
        await self.ensure_collection_ready()

        # Log collection info before building points
        self.logger.info(
            f"[Qdrant] bulk_insert: {len(entities)} entities → collection={self.collection_name}, "
            f"collection_id={self.collection_id}, vector_size={self.vector_size}"
        )

        point_structs = [self._build_point_struct(e) for e in entities]

        if not point_structs:
            self.logger.warning("No valid entities to insert")
            return

        # Try once with the whole payload; fall back to halving on failure
        # Track semaphore contention to understand queueing behavior
        available_slots = self._write_sem._value
        total_slots = self._write_limit
        active_writes = max(0, total_slots - available_slots)
        self.logger.info(
            f"[Qdrant] 🔒 Semaphore state: {active_writes}/{total_slots} "
            f"active writes before acquiring lock for {len(point_structs)} points"
        )

        max_batch = self._max_points_per_batch()
        adaptive_min_batch = max(2, min(8, max_batch // 8 if max_batch >= 8 else max_batch))

        async with self._write_sem:
            await self._upsert_points_with_fallback(point_structs, min_batch=adaptive_min_batch)

    # ----------------------------------------------------------------------------------
    # Deletes (by parent/sync/etc.)
    # ----------------------------------------------------------------------------------
    async def delete_by_sync_id(self, sync_id: UUID) -> None:
        """Delete all points that have the provided sync job id."""
        await self.ensure_client_readiness()
        async with self._write_sem:
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=rest.FilterSelector(
                    filter=rest.Filter(
                        must=[
                            # CRITICAL: Tenant filter for multi-tenant performance
                            rest.FieldCondition(
                                key="airweave_collection_id",
                                match=rest.MatchValue(value=str(self.collection_id)),
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
        async with self._write_sem:
            await self.client.delete(
                collection_name=self.collection_name,
                points_selector=rest.FilterSelector(
                    filter=rest.Filter(
                        must=[
                            # CRITICAL: Tenant filter for multi-tenant performance
                            rest.FieldCondition(
                                key="airweave_collection_id",
                                match=rest.MatchValue(value=str(self.collection_id)),
                            ),
                            rest.FieldCondition(
                                key="airweave_system_metadata.sync_id",
                                match=rest.MatchValue(value=str(sync_id)),
                            ),
                            rest.FieldCondition(
                                key="airweave_system_metadata.original_entity_id",
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
        *,
        limit: Optional[int] = None,
    ) -> dict:
        """Wrap an index search with optional decay formula (same semantics as old code)."""
        if decay_config is None:
            # Ensure a top-level limit is present for final result size
            if limit is None:
                try:
                    limit = int(params.get("limit")) if params.get("limit") is not None else None
                except Exception:
                    limit = None
            return {**params, **({"limit": limit} if limit is not None else {})}

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

        # Ensure a top-level limit is present for final result size
        if limit is None:
            try:
                limit = int(params.get("limit")) if params.get("limit") is not None else None
            except Exception:
                limit = None

        return {
            "prefetch": rest.Prefetch(**params),
            "query": rest.FormulaQuery(formula=weighted_formula),
            **({"limit": limit} if limit is not None else {}),
        }

    async def _prepare_query_request(  # noqa: C901
        self,
        dense_vector: list[float] | None,
        limit: int,
        sparse_vector: SparseEmbedding | dict | None,
        search_method: Literal["hybrid", "neural", "keyword"],
        decay_config: Optional[DecayConfig] = None,
        filter: Optional[rest.Filter] = None,
    ) -> rest.QueryRequest:
        """Create a single QueryRequest consistent with the old method."""
        query_request_params: dict = {}

        if search_method == "neural":
            if not dense_vector:
                raise ValueError("Neural search requires dense vector")
            neural_params = {
                "query": dense_vector,
                "using": DEFAULT_VECTOR_NAME,
                "limit": limit,
            }
            query_request_params = self._prepare_index_search_request(
                neural_params, decay_config, limit=limit
            )

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
            query_request_params = self._prepare_index_search_request(
                keyword_params, decay_config, limit=limit
            )

        if search_method == "hybrid":
            if not sparse_vector:
                raise ValueError("Hybrid search requires sparse vector")
            if not dense_vector:
                raise ValueError("Hybrid search requires dense vector")
            obj = (
                sparse_vector.as_object() if hasattr(sparse_vector, "as_object") else sparse_vector
            )

            # Prefetch limit controls how many candidates each neural/sparse branch fetches
            # before RRF fusion. Trade-off: higher = better recall, lower = less memory.
            # 5000 was causing OOM with expand_query (5 queries × 5000 × 2 = 50K vectors).
            # 1000 provides good recall while staying under memory limits.
            prefetch_limit = 1000
            if decay_config is not None:
                try:
                    weight = max(0.0, min(1.0, float(getattr(decay_config, "weight", 0.0) or 0.0)))
                    if weight > 0.3:
                        # Allow up to 2K for high temporal weight
                        prefetch_limit = int(1000 * (1 + weight))
                except Exception:
                    pass

            prefetch_params = [
                {
                    "query": dense_vector,
                    "using": DEFAULT_VECTOR_NAME,
                    "limit": prefetch_limit,
                    **({"filter": filter} if filter else {}),
                },
                {
                    "query": rest.SparseVector(**obj),
                    "using": KEYWORD_VECTOR_NAME,
                    "limit": prefetch_limit,
                    **({"filter": filter} if filter else {}),
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

        # Ensure top-level limit is set for final results
        query_request_params["limit"] = limit

        return rest.QueryRequest(**query_request_params)

    def _get_query_count(
        self,
        dense_vectors: list[list[float]] | None,
        sparse_vectors: list[SparseEmbedding] | list[dict] | None,
        search_method: Literal["hybrid", "neural", "keyword"],
    ) -> int:
        """Get number of queries based on search method and available vectors.

        Args:
            dense_vectors: Dense embeddings (None for keyword-only)
            sparse_vectors: Sparse embeddings (None for neural-only)
            search_method: Search strategy

        Returns:
            Number of queries

        Raises:
            ValueError: If required vectors are missing for the search method
        """
        if search_method == "keyword":
            if not sparse_vectors:
                raise ValueError("Keyword search requires sparse vectors")
            return len(sparse_vectors)
        else:
            if not dense_vectors:
                raise ValueError(f"{search_method} search requires dense vectors")
            return len(dense_vectors)

    def _validate_bulk_search_inputs(
        self,
        num_queries: int,
        filter_conditions: list[dict] | None,
        dense_vectors: list[list[float]] | None,
        sparse_vectors: list[SparseEmbedding] | list[dict] | None,
    ) -> None:
        """Validate lengths of per-query inputs for bulk search."""
        if filter_conditions and len(filter_conditions) != num_queries:
            raise ValueError(
                f"Number of filter conditions ({len(filter_conditions)}) must match "
                f"number of queries ({num_queries})"
            )
        if dense_vectors and sparse_vectors and len(dense_vectors) != len(sparse_vectors):
            raise ValueError("Sparse vector count does not match dense vectors")

    async def _prepare_bulk_search_requests(
        self,
        num_queries: int,
        dense_vectors: list[list[float]] | None,
        limit: int,
        score_threshold: float | None,
        with_payload: bool,
        filter_conditions: list[dict] | None,
        sparse_vectors: list[SparseEmbedding] | list[dict] | None,
        search_method: Literal["hybrid", "neural", "keyword"],
        decay_config: Optional[DecayConfig],
        offset: Optional[int],
    ) -> list[rest.QueryRequest]:
        """Create per-query request objects with automatic tenant filtering."""
        requests: list[rest.QueryRequest] = []
        for i in range(num_queries):
            dense_vector = dense_vectors[i] if dense_vectors else None
            # CRITICAL: Build tenant filter BEFORE preparing query request
            # This ensures prefetch operations are also filtered by tenant
            tenant_filter = rest.Filter(
                must=[
                    rest.FieldCondition(
                        key="airweave_collection_id",
                        match=rest.MatchValue(value=str(self.collection_id)),
                    )
                ]
            )

            # Merge with user-provided filters
            if filter_conditions and filter_conditions[i]:
                user_filter = rest.Filter.model_validate(filter_conditions[i])
                # Combine must conditions (tenant filter + user filters)
                combined_must = tenant_filter.must + (user_filter.must or [])
                combined_filter = rest.Filter(
                    must=combined_must,
                    should=user_filter.should,
                    must_not=user_filter.must_not,
                )
            else:
                combined_filter = tenant_filter

            sparse_vector = sparse_vectors[i] if sparse_vectors else None
            req = await self._prepare_query_request(
                dense_vector=dense_vector,
                limit=limit,
                sparse_vector=sparse_vector,
                search_method=search_method,
                decay_config=decay_config,
                filter=combined_filter,  # Pass filter to prefetch operations!
            )

            # Filter is already set via _prepare_query_request
            req.filter = combined_filter

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
    # Public search API (destination-agnostic interface)
    # ----------------------------------------------------------------------------------
    async def search(
        self,
        queries: List[str],
        airweave_collection_id: UUID,
        limit: int,
        offset: int,
        filter: Optional[dict] = None,
        dense_embeddings: Optional[List[List[float]]] = None,
        sparse_embeddings: Optional[List[Any]] = None,
        retrieval_strategy: str = "hybrid",
        temporal_config: Optional[AirweaveTemporalConfig] = None,
    ) -> List[AirweaveSearchResult]:
        """Execute search against Qdrant using pre-computed embeddings.

        Qdrant requires client-side embeddings (unlike Vespa which embeds server-side).
        The embeddings must be provided via the dense_embeddings parameter.

        Args:
            queries: List of search query texts (for logging only - Qdrant uses embeddings)
            airweave_collection_id: Airweave collection UUID for multi-tenant filtering
            limit: Maximum number of results to return
            offset: Number of results to skip (pagination)
            filter: Optional filter dict (Airweave canonical format, passed through)
            dense_embeddings: Pre-computed dense embeddings (required for Qdrant)
            sparse_embeddings: Pre-computed sparse embeddings for hybrid search
            retrieval_strategy: Search strategy - "hybrid", "neural", or "keyword"
            temporal_config: Optional temporal config (translated to DecayConfig internally)

        Returns:
            List of AirweaveSearchResult objects (unified format for all destinations)

        Raises:
            ValueError: If required embeddings are not provided for the strategy
        """
        # Keyword-only searches don't need dense embeddings
        if retrieval_strategy != RetrievalStrategy.KEYWORD.value and not dense_embeddings:
            raise ValueError(
                "Qdrant requires pre-computed dense embeddings for neural/hybrid search. "
                "Ensure EmbedQuery operation ran before Retrieval."
            )

        # Keyword searches require sparse embeddings
        if retrieval_strategy == RetrievalStrategy.KEYWORD.value and not sparse_embeddings:
            raise ValueError(
                "Keyword search requires sparse embeddings. "
                "Ensure EmbedQuery operation generated sparse embeddings."
            )

        # Translate temporal config to Qdrant-native DecayConfig
        decay_config = self.translate_temporal(temporal_config)

        # Filter already in dict format (Airweave canonical = Qdrant-compatible)
        filter_dict = self.translate_filter(filter)

        # Call bulk_search with appropriate vectors for the strategy
        # For keyword-only, dense vectors aren't needed (only sparse embeddings)
        dense_vectors_to_use = (
            None if retrieval_strategy == RetrievalStrategy.KEYWORD.value else dense_embeddings
        )

        # Get query count for filter conditions
        num_queries = self._get_query_count(
            dense_vectors_to_use, sparse_embeddings, retrieval_strategy
        )
        raw_results = await self.bulk_search(
            dense_vectors=dense_vectors_to_use,
            limit=limit,
            with_payload=True,
            filter_conditions=[filter_dict] * num_queries if filter_dict else None,
            sparse_vectors=sparse_embeddings,
            search_method=retrieval_strategy,
            decay_config=decay_config,
            offset=offset,
        )

        # Convert to unified AirweaveSearchResult format
        results = self._convert_to_airweave_results(raw_results)

        self.logger.debug(f"[QdrantSearch] Retrieved {len(results)} results")
        return results

    def _convert_to_airweave_results(self, raw_results: List[dict]) -> List[AirweaveSearchResult]:
        """Convert raw Qdrant results to AirweaveSearchResult format.

        Transforms Qdrant's payload structure into the unified AirweaveSearchResult
        format that matches what Vespa returns.

        Args:
            raw_results: List of raw result dicts from bulk_search

        Returns:
            List of AirweaveSearchResult objects
        """
        results = []
        for r in raw_results:
            payload = r.get("payload", {})

            # Extract system metadata from nested dict
            sys_meta = payload.get("airweave_system_metadata", {})
            system_metadata = SystemMetadataResult(
                entity_type=sys_meta.get("entity_type", ""),
                source_name=sys_meta.get("source_name"),
                sync_id=sys_meta.get("sync_id"),
                sync_job_id=sys_meta.get("sync_job_id"),
                original_entity_id=sys_meta.get("original_entity_id"),
                chunk_index=sys_meta.get("chunk_index"),
            )

            # Extract access control from nested dict
            access = None
            access_data = payload.get("access")
            if access_data:
                access = AccessControlResult(
                    is_public=access_data.get("is_public", False),
                    viewers=access_data.get("viewers", []),
                )

            # Extract breadcrumbs
            breadcrumbs = []
            raw_breadcrumbs = payload.get("breadcrumbs", [])
            if raw_breadcrumbs:
                for bc in raw_breadcrumbs:
                    if isinstance(bc, dict):
                        breadcrumbs.append(
                            BreadcrumbResult(
                                entity_id=bc.get("entity_id", ""),
                                name=bc.get("name", ""),
                                entity_type=bc.get("entity_type", ""),
                            )
                        )

            # Parse timestamps (Qdrant stores as ISO strings)
            created_at = None
            updated_at = None
            if payload.get("created_at"):
                try:
                    created_at = datetime.fromisoformat(
                        payload["created_at"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError, AttributeError):
                    pass
            if payload.get("updated_at"):
                try:
                    updated_at = datetime.fromisoformat(
                        payload["updated_at"].replace("Z", "+00:00")
                    )
                except (ValueError, TypeError, AttributeError):
                    pass

            # Build source_fields from remaining payload fields
            # Exclude known fields that are in the schema
            known_fields = {
                "entity_id",
                "name",
                "textual_representation",
                "created_at",
                "updated_at",
                "breadcrumbs",
                "airweave_system_metadata",
                "access",
            }
            source_fields = {k: v for k, v in payload.items() if k not in known_fields}

            result = AirweaveSearchResult(
                id=str(r.get("id", "")),
                score=r.get("score", 0.0),
                entity_id=payload.get("entity_id", ""),
                name=payload.get("name", ""),
                textual_representation=payload.get("textual_representation", ""),
                created_at=created_at,
                updated_at=updated_at,
                breadcrumbs=breadcrumbs,
                system_metadata=system_metadata,
                access=access,
                source_fields=source_fields,
            )
            results.append(result)

        return results

    def translate_filter(self, filter: Optional[dict]) -> Optional[dict]:
        """Translate filter to Qdrant dict format.

        Qdrant uses the Airweave canonical filter format natively, so this is passthrough.

        Args:
            filter: Airweave canonical filter dict

        Returns:
            Filter as dict, or None
        """
        if filter is None:
            return None
        # Convert Pydantic model to dict if needed (for safety)
        if hasattr(filter, "model_dump"):
            return filter.model_dump(exclude_none=True)
        return filter

    def translate_temporal(self, config: Optional[AirweaveTemporalConfig]) -> Optional[DecayConfig]:
        """Translate Airweave temporal config to Qdrant DecayConfig.

        Converts the destination-agnostic AirweaveTemporalConfig to Qdrant's
        native DecayConfig format.

        The TemporalRelevance operation sets target_datetime and scale_seconds
        dynamically based on actual collection data. If these are not set,
        fallback defaults are used.

        Args:
            config: Airweave temporal relevance configuration

        Returns:
            Qdrant DecayConfig, or None if config not provided
        """
        if config is None:
            return None

        # Use dynamic scale_seconds if set by TemporalRelevance operation,
        # otherwise parse decay_scale string, otherwise use 7 days default
        if config.scale_seconds is not None:
            scale_seconds = config.scale_seconds
        elif config.decay_scale:
            scale_seconds = self._parse_decay_scale(config.decay_scale)
        else:
            scale_seconds = 604800  # 7 days default

        # Use dynamic target_datetime if set by TemporalRelevance operation,
        # otherwise use current time
        target_datetime = config.target_datetime or datetime.now()

        return DecayConfig(
            decay_type="linear",
            datetime_field=config.reference_field,
            target_datetime=target_datetime,
            scale_seconds=scale_seconds,
            midpoint=0.5,
            weight=config.weight,
        )

    def _parse_decay_scale(self, scale: str) -> float:
        """Parse decay scale string to seconds.

        Args:
            scale: Scale string like "7d", "30d", "1h"

        Returns:
            Scale in seconds
        """
        scale = scale.lower().strip()
        if scale.endswith("d"):
            return float(scale[:-1]) * 86400  # days to seconds
        elif scale.endswith("h"):
            return float(scale[:-1]) * 3600  # hours to seconds
        elif scale.endswith("m"):
            return float(scale[:-1]) * 60  # minutes to seconds
        elif scale.endswith("s"):
            return float(scale[:-1])  # seconds
        else:
            # Assume days if no unit
            return float(scale) * 86400

    async def bulk_search(
        self,
        dense_vectors: list[list[float]] | None,
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

        # Calculate query count once and validate inputs
        num_queries = self._get_query_count(dense_vectors, sparse_vectors, search_method)
        self._validate_bulk_search_inputs(
            num_queries, filter_conditions, dense_vectors, sparse_vectors
        )

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
            f"queries={num_queries}, limit={limit}, "
            f"has_sparse={sparse_vectors is not None}, "
            f"decay_enabled={decay_config is not None}, "
            f"decay_weight={weight}"
        )

        if decay_config:
            decay_weight = getattr(decay_config, "weight", 0)
            decay_field = decay_config.datetime_field
            decay_scale = getattr(decay_config, "scale_seconds", None)
            self.logger.debug(
                "[Qdrant] Decay strategy: weight=%.1f, field=%s, scale=%ss",
                decay_weight,
                decay_field,
                decay_scale,
            )

        try:
            requests = await self._prepare_bulk_search_requests(
                num_queries=num_queries,
                dense_vectors=dense_vectors,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=with_payload,
                filter_conditions=filter_conditions or [None] * num_queries,
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
    # Health & Diagnostics
    # ----------------------------------------------------------------------------------
    async def get_collection_health_info(self) -> dict:
        """Get comprehensive collection health and statistics for diagnostics.

        Returns:
            Dict with collection size, segment count, indexing status, etc.
        """
        await self.ensure_client_readiness()
        health_info = {
            "collection_name": self.collection_name,
            "collection_id": str(self.collection_id),
            "vector_size": self.vector_size,
        }

        try:
            # Get collection info
            info = await self.client.get_collection(collection_name=self.collection_name)

            # Extract key metrics
            health_info["points_count"] = info.points_count
            health_info["indexed_vectors_count"] = info.indexed_vectors_count
            health_info["vectors_count"] = info.vectors_count
            health_info["status"] = (
                info.status.value if hasattr(info.status, "value") else str(info.status)
            )

            # Segment info
            if hasattr(info, "segments_count"):
                health_info["segments_count"] = info.segments_count

            # Optimizer status
            if info.optimizer_status:
                health_info["optimizer_ok"] = info.optimizer_status.ok
                if hasattr(info.optimizer_status, "error"):
                    health_info["optimizer_error"] = info.optimizer_status.error

            # Payload schema
            if info.payload_schema:
                health_info["indexed_fields"] = list(info.payload_schema.keys())

        except Exception as e:
            health_info["error"] = f"Failed to fetch collection info: {type(e).__name__}: {str(e)}"

        return health_info

    # ----------------------------------------------------------------------------------
    # Introspection
    # ----------------------------------------------------------------------------------
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
