"""Vespa destination implementation.

Vespa stores entities with pre-computed chunks and embeddings as arrays.
The VespaChunkEmbedProcessor handles chunking and embedding externally,
storing results in entity.vespa_content which this destination transforms
to Vespa's tensor format.

IMPORTANT: pyvespa methods are synchronous and would block the event loop.
All pyvespa calls are wrapped in asyncio.to_thread() to maintain concurrency.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union
from urllib.parse import quote
from uuid import UUID

import httpx

from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.platform.decorators import destination
from airweave.platform.destinations._base import VectorDBDestination
from airweave.platform.entities._base import (
    AirweaveSystemMetadata,
    BaseEntity,
    CodeFileEntity,
    EmailEntity,
    FileEntity,
    WebEntity,
)
from airweave.schemas.search import AirweaveTemporalConfig, SearchResult

if TYPE_CHECKING:
    from vespa.application import Vespa


def _get_system_metadata_fields() -> set[str]:
    """Get system metadata fields from AirweaveSystemMetadata class.

    Derives the field set dynamically from AirweaveSystemMetadata.model_fields,
    ensuring this stays in sync with the entity definitions (single source of truth).

    Returns:
        Set of field names that are system metadata (not payload)
    """
    # Get fields from the actual AirweaveSystemMetadata class
    fields = set(AirweaveSystemMetadata.model_fields.keys())

    # Add the parent field name itself (it's excluded from entity_dict)
    fields.add("airweave_system_metadata")

    # Derived field from sync context (not part of the Pydantic model)
    fields.add("collection_id")

    return fields


def _get_schema_fields_for_entity(entity: BaseEntity) -> set[str]:
    """Get all fields that have Vespa schema columns (not payload) for an entity.

    This derives the field list dynamically from the entity class hierarchy,
    making the entity class definitions the single source of truth.

    Args:
        entity: The entity to get schema fields for

    Returns:
        Set of field names that should NOT go into the payload JSON
    """
    # Start with BaseEntity fields
    fields = set(BaseEntity.model_fields.keys())

    # Add system metadata fields (derived dynamically)
    fields |= _get_system_metadata_fields()

    # Add type-specific fields based on entity class hierarchy
    if isinstance(entity, WebEntity):
        # WebEntity adds crawl_url
        fields |= set(WebEntity.model_fields.keys()) - set(BaseEntity.model_fields.keys())
    if isinstance(entity, FileEntity):
        # FileEntity adds url, size, file_type, mime_type, local_path
        fields |= set(FileEntity.model_fields.keys()) - set(BaseEntity.model_fields.keys())
    if isinstance(entity, CodeFileEntity):
        # CodeFileEntity adds repo_name, path_in_repo, repo_owner, language, commit_id
        fields |= set(CodeFileEntity.model_fields.keys()) - set(FileEntity.model_fields.keys())
    # EmailEntity doesn't add any fields beyond FileEntity

    return fields


@destination(
    "Vespa",
    "vespa",
    supports_vector=True,
    requires_client_embedding=True,  # We now embed externally
    supports_temporal_relevance=False,
)
class VespaDestination(VectorDBDestination):
    """Vespa destination with external chunking and embedding.

    Uses VespaChunkEmbedProcessor to chunk text and compute embeddings externally,
    storing them in entity.vespa_content as arrays. This destination transforms
    those arrays to Vespa's tensor format for efficient storage and retrieval.
    """

    # Use VespaChunkEmbedProcessor for external chunking/embedding
    from airweave.platform.sync.pipeline import ProcessingRequirement

    processing_requirement = ProcessingRequirement.VESPA_CHUNKS_AND_EMBEDDINGS

    def __init__(self):
        """Initialize the Vespa destination."""
        super().__init__()
        self.collection_id: UUID | None = None
        self.sync_id: UUID | None = None
        self.organization_id: UUID | None = None
        self.app: Optional[Vespa] = None

    @classmethod
    async def create(
        cls,
        credentials: Optional[any] = None,
        config: Optional[dict] = None,
        collection_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
        vector_size: Optional[int] = None,
        logger: Optional[ContextualLogger] = None,
        **kwargs,
    ) -> "VespaDestination":
        """Create and return a connected Vespa destination.

        Args:
            credentials: Optional credentials (unused for native Vespa)
            config: Optional configuration (unused)
            collection_id: SQL collection UUID for multi-tenant filtering
            organization_id: Organization UUID
            vector_size: Vector dimensions (unused - Vespa handles embeddings)
            logger: Logger instance
            **kwargs: Additional keyword arguments (unused)

        Returns:
            Configured VespaDestination instance
        """
        from vespa.application import Vespa

        instance = cls()
        instance.set_logger(logger or default_logger)
        instance.collection_id = collection_id
        instance.organization_id = organization_id

        # Connect to Vespa
        instance.app = Vespa(url=settings.VESPA_URL, port=settings.VESPA_PORT)

        instance.logger.info(
            f"Connected to Vespa at {settings.vespa_url} for collection {collection_id}"
        )

        return instance

    def _get_vespa_schema(self, entity: BaseEntity) -> str:
        """Determine the Vespa schema name for an entity.

        Args:
            entity: The entity to get schema for

        Returns:
            Vespa schema name (e.g., "base_entity", "file_entity", "code_file_entity")
        """
        # Check in order of specificity (most specific first)
        if isinstance(entity, CodeFileEntity):
            return "code_file_entity"
        elif isinstance(entity, EmailEntity):
            return "email_entity"
        elif isinstance(entity, FileEntity):
            return "file_entity"
        elif isinstance(entity, WebEntity):
            return "web_entity"
        else:
            return "base_entity"

    def _transform_entity(self, entity: BaseEntity) -> tuple[str, dict]:
        """Transform BaseEntity to Vespa document format.

        Args:
            entity: The entity to transform

        Returns:
            Tuple of (schema_name, doc_dict) where doc_dict has 'id' and 'fields' keys
        """
        entity_type = self._get_entity_type(entity)
        schema = self._get_vespa_schema(entity)
        doc_id = f"{entity_type}_{entity.entity_id}"

        # Build fields from various sources
        fields = self._build_base_fields(entity)
        self._add_system_metadata_fields(fields, entity, entity_type)
        self._add_type_specific_fields(fields, entity)
        self._add_vespa_content_fields(fields, entity)  # Add chunks and embeddings
        self._add_payload_field(fields, entity)

        # Remove None values from top-level fields
        fields = {k: v for k, v in fields.items() if v is not None}

        return schema, {"id": doc_id, "fields": fields}

    def _get_entity_type(self, entity: BaseEntity) -> str:
        """Get entity type from metadata or class name."""
        if entity.airweave_system_metadata and entity.airweave_system_metadata.entity_type:
            return entity.airweave_system_metadata.entity_type
        return entity.__class__.__name__

    def _build_base_fields(self, entity: BaseEntity) -> dict[str, Any]:
        """Build base fields dict from entity."""
        fields: dict[str, Any] = {
            "entity_id": entity.entity_id,
            "name": entity.name,
        }
        if entity.breadcrumbs:
            fields["breadcrumbs"] = [b.model_dump() for b in entity.breadcrumbs]
        if entity.created_at:
            fields["created_at"] = int(entity.created_at.timestamp())
        if entity.updated_at:
            fields["updated_at"] = int(entity.updated_at.timestamp())
        if entity.textual_representation:
            fields["textual_representation"] = entity.textual_representation
        return fields

    def _add_system_metadata_fields(
        self, fields: dict[str, Any], entity: BaseEntity, entity_type: str
    ) -> None:
        """Add flattened system metadata fields with airweave_system_metadata_ prefix."""
        meta_fields = self._build_system_metadata(entity)

        # Add collection_id if available
        if self.collection_id:
            meta_fields["collection_id"] = str(self.collection_id)

        # Ensure critical metadata is always present
        meta_fields.setdefault("entity_type", entity_type)
        if "original_entity_id" not in meta_fields and entity.entity_id:
            meta_fields["original_entity_id"] = entity.entity_id

        for key, value in meta_fields.items():
            if value is not None:
                fields[f"airweave_system_metadata_{key}"] = value

    def _build_system_metadata(self, entity: BaseEntity) -> dict[str, Any]:
        """Extract system metadata from entity."""
        meta_fields: dict[str, Any] = {}
        meta = entity.airweave_system_metadata
        if not meta:
            return meta_fields

        # Map attribute names to field names and optional transforms
        attr_mappings = [
            ("entity_type", "entity_type", None),
            ("sync_id", "sync_id", str),
            ("sync_job_id", "sync_job_id", str),
            ("hash", "hash", None),
            ("original_entity_id", "original_entity_id", None),
            ("source_name", "source_name", None),
        ]

        for attr, field_name, transform in attr_mappings:
            value = getattr(meta, attr, None)
            if value is not None:
                meta_fields[field_name] = transform(value) if transform else value

        return meta_fields

    def _add_type_specific_fields(self, fields: dict[str, Any], entity: BaseEntity) -> None:
        """Add fields specific to entity subtype (WebEntity, FileEntity, etc.)."""
        if isinstance(entity, WebEntity):
            fields["crawl_url"] = entity.crawl_url
        elif isinstance(entity, CodeFileEntity):
            fields["repo_name"] = entity.repo_name
            fields["path_in_repo"] = entity.path_in_repo
            fields["repo_owner"] = entity.repo_owner
            fields["language"] = entity.language
            fields["commit_id"] = entity.commit_id
        elif isinstance(entity, FileEntity):
            fields["url"] = entity.url
            fields["size"] = entity.size
            fields["file_type"] = entity.file_type
            if entity.mime_type:
                fields["mime_type"] = entity.mime_type
            if entity.local_path:
                fields["local_path"] = entity.local_path

    def _add_vespa_content_fields(self, fields: dict[str, Any], entity: BaseEntity) -> None:
        """Add pre-computed chunks and embeddings from VespaContent.

        VespaChunkEmbedProcessor populates entity.vespa_content with:
        - chunks: List[str] - chunked text segments
        - chunk_small_embeddings: List[List[int]] - binary-packed for ANN (96 int8)
        - chunk_large_embeddings: List[List[float]] - full precision for ranking (768 dim)

        This method transforms those to Vespa's tensor format.

        Args:
            fields: Fields dict to update
            entity: The entity to extract vespa_content from
        """
        vc = entity.vespa_content
        if vc is None:
            return

        # Chunks array - direct assignment
        if vc.chunks:
            fields["chunks"] = vc.chunks

        # Small embeddings - transform to Vespa tensor format (int8)
        if vc.chunk_small_embeddings:
            fields["chunk_small_embeddings"] = self._to_vespa_tensor(
                vc.chunk_small_embeddings, indexed_dim=96
            )

        # Large embeddings - transform to Vespa tensor format (bfloat16)
        if vc.chunk_large_embeddings:
            fields["chunk_large_embeddings"] = self._to_vespa_tensor(
                vc.chunk_large_embeddings, indexed_dim=768
            )

    def _to_vespa_tensor(self, embeddings: List[List[Union[int, float]]], indexed_dim: int) -> dict:
        """Convert Python list of embeddings to Vespa tensor format.

        Vespa expects tensors with mixed dimensions (mapped + indexed) in cell format:
        {"cells": [{"address": {"chunk": "0", "x": "0"}, "value": v}, ...]}

        For tensor<int8>(chunk{}, x[96]) or tensor<bfloat16>(chunk{}, x[768]):
        - chunk{} is a mapped dimension (sparse, labeled)
        - x[N] is an indexed dimension (dense, positional)

        Args:
            embeddings: List of embedding vectors (one per chunk)
            indexed_dim: Expected dimension of each embedding

        Returns:
            Vespa tensor dict with cells format
        """
        cells = []
        for chunk_idx, embedding in enumerate(embeddings):
            for x_idx, value in enumerate(embedding):
                cells.append(
                    {"address": {"chunk": str(chunk_idx), "x": str(x_idx)}, "value": value}
                )
        return {"cells": cells}

    def _add_payload_field(self, fields: dict[str, Any], entity: BaseEntity) -> None:
        """Extract extra fields into payload JSON."""
        schema_fields = _get_schema_fields_for_entity(entity)
        entity_dict = entity.model_dump(mode="json")
        payload = {k: v for k, v in entity_dict.items() if k not in schema_fields}
        if payload:
            fields["payload"] = json.dumps(payload)

    def _transform_entities_by_schema(self, entities: list[BaseEntity]) -> dict[str, list[dict]]:
        """Transform entities and group by Vespa schema."""
        docs_by_schema: dict[str, list[dict]] = defaultdict(list)
        for entity in entities:
            try:
                schema, vespa_doc = self._transform_entity(entity)
                docs_by_schema[schema].append(vespa_doc)
            except Exception as e:
                self.logger.error(f"Failed to transform entity {entity.entity_id}: {e}")
        return docs_by_schema

    async def setup_collection(self, vector_size: int | None = None) -> None:
        """Set up collection in Vespa.

        Note: Vespa schema is deployed separately via vespa-deploy.
        This method is a no-op but kept for interface compatibility.
        """
        self.logger.debug("Vespa schema is managed via vespa-deploy, skipping setup_collection")

    async def bulk_insert(self, entities: list[BaseEntity]) -> None:  # noqa: C901
        """Transform entities and batch feed to Vespa using feed_iterable.

        Uses pyvespa's feed_iterable for efficient concurrent feeding via HTTP/2
        multiplexing. This is much faster than sequential feed_data_point calls.

        Entities are grouped by schema type and fed separately to the correct schema.

        IMPORTANT: feed_iterable is synchronous, so we run it in a thread pool
        to avoid blocking the async event loop.

        Args:
            entities: List of entities to insert
        """
        if not entities:
            return

        if not self.app:
            raise RuntimeError("Vespa client not initialized. Call create() first.")

        total_start = time.perf_counter()
        self.logger.info(f"[VespaDestination] Starting bulk_insert for {len(entities)} entities")

        # Transform all entities to Vespa format, grouped by schema
        transform_start = time.perf_counter()
        docs_by_schema = self._transform_entities_by_schema(entities)
        total_docs = sum(len(docs) for docs in docs_by_schema.values())
        transform_ms = (time.perf_counter() - transform_start) * 1000

        # Count total chunks being fed
        total_chunks = 0
        for entity in entities:
            if entity.vespa_content and entity.vespa_content.chunks:
                total_chunks += len(entity.vespa_content.chunks)

        self.logger.info(
            f"[VespaDestination] Transform: {transform_ms:.1f}ms for {len(entities)} entities "
            f"→ {total_docs} docs with {total_chunks} total chunks"
        )

        if total_docs == 0:
            self.logger.warning("No documents to feed after transformation")
            return

        # Track results via callback (must be thread-safe since feed_iterable uses threads)
        success_count = 0
        failed_docs: list[tuple[str, int, dict]] = []

        def callback(response, doc_id: str):
            nonlocal success_count
            if response.is_successful():
                success_count += 1
            else:
                failed_docs.append((doc_id, response.status_code, response.json))

        # Define the synchronous feed operation for a specific schema
        def _feed_schema_sync(schema: str, docs: list[dict]):
            self.app.feed_iterable(
                iter=docs,
                schema=schema,
                namespace="airweave",
                callback=callback,
                max_queue_size=500,
                max_workers=16,
                max_connections=16,
            )

        # Feed each schema's documents
        feed_start = time.perf_counter()
        for schema, docs in docs_by_schema.items():
            schema_start = time.perf_counter()
            self.logger.debug(
                f"[VespaDestination] Feeding {len(docs)} documents to schema '{schema}'"
            )
            await asyncio.to_thread(_feed_schema_sync, schema, docs)
            schema_ms = (time.perf_counter() - schema_start) * 1000
            self.logger.info(
                f"[VespaDestination] Fed schema '{schema}': {len(docs)} docs in {schema_ms:.1f}ms "
                f"({schema_ms / len(docs):.1f}ms/doc)"
            )
        feed_ms = (time.perf_counter() - feed_start) * 1000

        total_ms = (time.perf_counter() - total_start) * 1000
        self.logger.info(
            f"[VespaDestination] TOTAL bulk_insert: {total_ms:.1f}ms | "
            f"transform={transform_ms:.0f}ms, feed={feed_ms:.0f}ms | "
            f"{success_count} success, {len(failed_docs)} failed"
        )

        if failed_docs:
            self._handle_feed_failures(failed_docs, total_docs)

    def _handle_feed_failures(
        self, failed_docs: list[tuple[str, int, dict]], total_docs: int
    ) -> None:
        """Log and raise error for feed failures."""
        self.logger.error(f"{len(failed_docs)}/{total_docs} documents failed to feed")
        # Log first few failures for debugging
        for doc_id, status, body in failed_docs[:5]:
            self.logger.error(f"  Failed {doc_id}: status={status}, body={body}")

        # Raise exception to fail the sync - consistent with QdrantDestination behavior
        first_doc_id, first_status, first_body = failed_docs[0]
        error_msg = (
            first_body.get("Exception", str(first_body))
            if isinstance(first_body, dict)
            else str(first_body)
        )
        raise RuntimeError(
            f"Vespa feed failed: {len(failed_docs)}/{total_docs} documents. "
            f"First error ({first_doc_id}): {error_msg}"
        )

    # Vespa schema names derived from entity class hierarchy
    # These match the _get_vespa_schema() method mapping
    @staticmethod
    def _get_all_vespa_schemas() -> list[str]:
        """Get all Vespa schema names.

        Derives from entity class names to stay in sync with _get_vespa_schema().
        Converting CamelCase to snake_case for Vespa schema names.

        Returns:
            List of all Vespa schema names
        """
        entity_classes = [BaseEntity, FileEntity, CodeFileEntity, EmailEntity, WebEntity]
        return [VespaDestination._class_to_schema_name(cls) for cls in entity_classes]

    @staticmethod
    def _class_to_schema_name(cls: type) -> str:
        """Convert entity class name to Vespa schema name.

        Args:
            cls: Entity class

        Returns:
            Snake_case schema name (e.g., CodeFileEntity -> code_file_entity)
        """
        import re

        # Convert CamelCase to snake_case
        name = cls.__name__
        # Insert underscore before uppercase letters and lowercase
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    async def delete_by_sync_id(self, sync_id: UUID) -> None:
        """Delete all documents from a sync run using selection-based bulk delete.

        Uses Vespa's /document/v1 DELETE with selection parameter for efficient
        server-side deletion instead of fetching IDs and deleting one-by-one.

        Args:
            sync_id: The sync ID to delete documents for
        """
        if not self.app:
            raise RuntimeError("Vespa client not initialized")

        # Delete from all schemas (each schema handles its own field qualification)
        for schema in self._get_all_vespa_schemas():
            # Build schema-qualified selection expression
            # Note: Document selection language requires explicit schema.field references
            selection = (
                f"{schema}.airweave_system_metadata_sync_id=='{sync_id}' and "
                f"{schema}.airweave_system_metadata_collection_id=='{self.collection_id}'"
            )
            await self._delete_by_selection(schema, selection)

    async def delete_by_collection_id(self, collection_id: UUID) -> None:
        """Delete all documents for a collection using selection-based bulk delete.

        Uses Vespa's /document/v1 DELETE with selection parameter for efficient
        server-side deletion instead of fetching IDs and deleting one-by-one.

        Args:
            collection_id: The collection ID to delete documents for
        """
        if not self.app:
            raise RuntimeError("Vespa client not initialized")

        # Delete from all schemas (each schema handles its own field qualification)
        for schema in self._get_all_vespa_schemas():
            # Build schema-qualified selection expression
            # Note: Document selection language requires explicit schema.field references
            selection = f"{schema}.airweave_system_metadata_collection_id=='{collection_id}'"
            await self._delete_by_selection(schema, selection)

    async def _delete_by_selection(self, schema: str, selection: str) -> int:
        """Delete documents using Vespa's selection-based bulk delete API.

        This is MUCH faster than query-then-delete because it performs server-side
        deletion in a single streaming operation rather than individual HTTP calls.

        Uses: DELETE /document/v1/{namespace}/{doctype}/docid?selection={expr}&cluster={cluster}

        Args:
            schema: The Vespa schema/document type to delete from
            selection: Document selection expression with schema-qualified field names
                       (e.g., "base_entity.field=='value'")
                       Note: Vespa's document selection language (different from YQL) requires
                       explicit schema.field references unlike the YQL `from` clause.

        Returns:
            Number of documents deleted (estimated from response)
        """
        url = self._build_bulk_delete_url(schema, selection)
        self.logger.debug(f"[Vespa] Bulk delete from {schema} with selection: {selection}")

        deleted_count = 0
        try:
            deleted_count = await self._execute_bulk_delete(url, schema)
        except httpx.TimeoutException:
            self.logger.error(f"[Vespa] Bulk delete timed out after {settings.VESPA_TIMEOUT}s")
        except Exception as e:
            self.logger.error(f"[Vespa] Bulk delete error: {e}")

        return deleted_count

    def _build_bulk_delete_url(self, schema: str, selection: str) -> str:
        """Build the URL for Vespa bulk delete operation."""
        base_url = f"{settings.VESPA_URL}:{settings.VESPA_PORT}"
        encoded_selection = quote(selection, safe="")
        return (
            f"{base_url}/document/v1/airweave/{schema}/docid"
            f"?selection={encoded_selection}"
            f"&cluster={settings.VESPA_CLUSTER}"
        )

    async def _execute_bulk_delete(self, url: str, schema: str) -> int:
        """Execute bulk delete request and parse response.

        Args:
            url: The bulk delete URL
            schema: Schema name for logging

        Returns:
            Number of documents deleted
        """
        deleted_count = 0
        async with httpx.AsyncClient(timeout=settings.VESPA_TIMEOUT) as client:
            async with client.stream("DELETE", url) as response:
                if response.status_code == 200:
                    deleted_count = await self._parse_bulk_delete_response(response)
                else:
                    await self._log_delete_error(response)

        if deleted_count > 0:
            self.logger.info(f"[Vespa] Deleted {deleted_count} documents from {schema}")
        else:
            self.logger.debug(f"[Vespa] No documents to delete from {schema}")

        return deleted_count

    async def _parse_bulk_delete_response(self, response: httpx.Response) -> int:
        """Parse streaming response from Vespa bulk delete.

        Vespa returns JSON lines with documentCount for bulk deletes.
        Format: {"pathId":"/document/v1/...","documentCount":N}
        """
        count = 0
        async for line in response.aiter_lines():
            if not line.strip():
                continue
            try:
                result = json.loads(line)
                # Get document count from bulk delete response
                if "documentCount" in result:
                    count += result["documentCount"]
                # Also handle individual document deletions (id field)
                elif result.get("id"):
                    count += 1
            except json.JSONDecodeError:
                pass  # Skip malformed lines
        return count

    async def _log_delete_error(self, response: httpx.Response) -> None:
        """Log error from failed bulk delete response."""
        body = await response.aread()
        if response.status_code == 400:
            self.logger.error(f"[Vespa] Invalid selection expression: {body.decode()}")
        else:
            self.logger.error(
                f"[Vespa] Bulk delete failed ({response.status_code}): {body.decode()}"
            )

    async def bulk_delete_by_parent_ids(self, parent_ids: list[str], sync_id: UUID) -> None:
        """Delete all documents for multiple parent IDs using selection-based bulk delete.

        Batches parent IDs into groups to create efficient OR selections rather than
        making individual delete calls per parent ID.

        Args:
            parent_ids: List of parent entity IDs
            sync_id: The sync ID for scoping
        """
        if not parent_ids or not self.app:
            return

        # Batch parent IDs to avoid overly long selection expressions
        batch_size = 50  # Keep selection expressions manageable
        for i in range(0, len(parent_ids), batch_size):
            batch = parent_ids[i : i + batch_size]

            # Build OR selection for this batch of parent IDs
            parent_conditions = " or ".join(
                f"airweave_system_metadata_original_entity_id=='{pid}'" for pid in batch
            )
            selection = (
                f"({parent_conditions}) and "
                f"airweave_system_metadata_collection_id=='{self.collection_id}'"
            )

            # Delete from all schemas
            for schema in self._get_all_vespa_schemas():
                await self._delete_by_selection(schema, selection)

    # Production search settings (100k+ entities, LLM input)
    # targetHits: 400 per method → ~800 candidates before deduplication
    # rerank-count: 200 (second phase), 100 (global phase)
    # Final output: up to 100 results
    TARGET_HITS = 400  # Candidate pool per retrieval method

    async def search(
        self,
        queries: List[str],
        airweave_collection_id: UUID,
        limit: int,
        offset: int,
        filter: Optional[Dict[str, Any]] = None,
        dense_embeddings: Optional[List[List[float]]] = None,
        sparse_embeddings: Optional[List[Any]] = None,
        retrieval_strategy: str = "hybrid",
        temporal_config: Optional[AirweaveTemporalConfig] = None,
    ) -> List[SearchResult]:
        """Execute hybrid search against Vespa with multi-query support.

        Embeddings are pre-computed externally via DenseEmbedder and passed as
        tensor parameters. This eliminates server-side embedding computation.

        Multi-Query Support:
            When query expansion provides multiple queries (primary + expanded), each
            query gets its own nearestNeighbor operator combined with OR. This improves
            recall by retrieving documents similar to any of the query variants.

        Note: temporal_config is accepted for interface compatibility but ignored.
        Vespa temporal relevance ranking is not yet implemented.

        Args:
            queries: List of search query texts. First query is primary (used for
                userInput/lexical). All queries are used for nearestNeighbor/semantic.
            airweave_collection_id: Airweave collection UUID for multi-tenant filtering
            limit: Maximum number of results to return
            offset: Number of results to skip (pagination)
            filter: Optional filter dict (translated to YQL WHERE clause)
            dense_embeddings: Pre-computed 768-dim embeddings (one per query).
                             If None, will be computed via DenseEmbedder.
            sparse_embeddings: Ignored - Vespa handles BM25 server-side
            retrieval_strategy: Search strategy (currently always hybrid)
            temporal_config: Ignored - temporal relevance not yet supported for Vespa

        Returns:
            List of SearchResult objects
        """
        if not self.app:
            raise RuntimeError("Vespa client not initialized. Call create() first.")

        # Use first query as primary (for logging and userInput)
        primary_query = queries[0] if queries else ""

        # Log query expansion usage
        if len(queries) > 1:
            self.logger.info(
                f"[VespaSearch] Using query expansion with {len(queries)} queries "
                f"(primary + {len(queries) - 1} expanded)"
            )

        self.logger.debug(
            f"[VespaSearch] Executing search: query='{primary_query[:50]}...', "
            f"num_queries={len(queries)}, limit={limit}, has_filter={filter is not None}"
        )

        # Use provided embeddings if they have correct dimensions (768-dim)
        # Otherwise, re-embed with Matryoshka truncation to 768-dim
        VESPA_EMBEDDING_DIM = 768  # Must match base_entity.sd chunk_large_embeddings
        if (
            dense_embeddings
            and len(dense_embeddings) == len(queries)
            and len(dense_embeddings[0]) == VESPA_EMBEDDING_DIM
        ):
            # Use provided embeddings - just binary-pack for ANN search
            large_embeddings = dense_embeddings
            small_embeddings = [self._pack_bits_for_query(emb) for emb in large_embeddings]
            self.logger.info(
                f"[VespaSearch] Using provided {VESPA_EMBEDDING_DIM}-dim embeddings "
                f"(no re-embedding needed)"
            )
        else:
            # Re-embed with correct dimensions (fallback - should rarely happen now)
            provided_dim = len(dense_embeddings[0]) if dense_embeddings else 0
            self.logger.info(
                f"[VespaSearch] Re-embedding: provided={provided_dim}-dim, "
                f"required={VESPA_EMBEDDING_DIM}-dim"
            )
            large_embeddings, small_embeddings = await self._embed_queries(queries)

        # Translate filter to YQL clause (if present)
        yql_filter = self.translate_filter(filter) if filter else None

        # Build YQL with proper filter injection and multi-query support
        yql = self._build_search_yql(queries, airweave_collection_id, yql_filter)

        # Build query parameters with pre-computed embeddings
        query_params = self._build_query_params(
            queries, primary_query, limit, offset, large_embeddings, small_embeddings
        )
        query_params["yql"] = yql

        self.logger.debug(f"[VespaSearch] YQL: {yql}")

        # DEBUG: Log full query params (excluding large embedding values)
        debug_params = {k: v for k, v in query_params.items() if k != "yql"}
        for key in list(debug_params.keys()):
            if "embedding" in key.lower() or key.startswith("input.query"):
                debug_params[key] = f"<tensor with {len(str(debug_params[key]))} chars>"
        self.logger.info(
            f"[VespaSearch] QUERY PARAMS:\n  YQL: {yql}\n  Other params: {debug_params}"
        )

        # Execute query in thread pool (pyvespa is synchronous)
        import time

        start_time = time.monotonic()
        try:
            response = await asyncio.to_thread(self.app.query, body=query_params)
        except Exception as e:
            self.logger.error(f"[VespaSearch] Vespa query failed: {e}")
            raise RuntimeError(f"Vespa search failed: {e}") from e
        query_time_ms = (time.monotonic() - start_time) * 1000

        # Check for errors
        if not response.is_successful():
            error_msg = getattr(response, "json", {}).get("error", str(response))
            self.logger.error(f"[VespaSearch] Vespa returned error: {error_msg}")
            raise RuntimeError(f"Vespa search error: {error_msg}")

        # DEBUG: Log Vespa internal metrics
        try:
            raw_json = response.json if hasattr(response, "json") else {}
            root = raw_json.get("root", {})
            coverage = root.get("coverage", {})
            timing = raw_json.get("timing", {})
            total_count = root.get("fields", {}).get("totalCount", 0)

            self.logger.info(
                f"\n[VespaSearch] VESPA METRICS:\n"
                f"  Query time (client): {query_time_ms:.1f}ms\n"
                f"  Vespa timing: {timing}\n"
                f"  Total matching docs: {total_count}\n"
                f"  Coverage: {coverage.get('coverage', 100)}% "
                f"({coverage.get('documents', 0)} docs, {coverage.get('nodes', 0)} nodes)\n"
                f"  Hits returned: {len(response.hits) if response.hits else 0}"
            )
        except Exception as e:
            self.logger.debug(f"[VespaSearch] Could not extract metrics: {e}")

        # Convert Vespa results to SearchResult format
        raw_results = self._convert_vespa_results(response)

        # Apply offset (pagination)
        if offset > 0:
            raw_results = raw_results[offset:]

        # Limit results
        final_results = raw_results[:limit]

        self.logger.debug(f"[VespaSearch] Retrieved {len(final_results)} results")

        return final_results

    def _build_search_yql(
        self,
        queries: List[str],
        airweave_collection_id: UUID,
        yql_filter: Optional[str] = None,
    ) -> str:
        """Build YQL query with hybrid retrieval and multi-query support.

        Combines lexical (userInput/weakAnd) and semantic (nearestNeighbor) retrieval
        with collection filtering and optional user filters.

        Multi-Query Support (Query Expansion):
            When multiple queries are provided (primary + expanded), creates a separate
            nearestNeighbor operator for each query, combined with OR. This allows
            expanded queries from query expansion to participate in retrieval.

            Example YQL for 2 queries:
                ({label:"q0", targetHits:400}nearestNeighbor(chunk_small_embeddings, q0) OR
                 {label:"q1", targetHits:400}nearestNeighbor(chunk_small_embeddings, q1))

            The rank profile's closeness(field, chunk_small_embeddings) automatically
            returns the maximum closeness across all operators. Labels (q0, q1, etc.)
            can be used with closeness(label, q0) for per-query similarity if needed.

        Args:
            queries: List of search query texts (primary + expanded)
            airweave_collection_id: Airweave collection UUID for multi-tenant filtering
            yql_filter: Optional translated filter clause (e.g., "source_name contains 'GitHub'")

        Returns:
            Complete YQL query string
        """
        # Build nearestNeighbor operators for all queries
        # Use labels (q0, q1, q2, ...) so closeness can be computed per query
        # Each annotated operator must be wrapped in parentheses for YQL parsing
        nn_parts = []
        for i in range(len(queries)):
            # Use label annotation to distinguish closeness from different queries
            # Wrap in parens - required for YQL parsing after OR
            nn_parts.append(
                f'({{label:"q{i}", targetHits:{self.TARGET_HITS}}}'
                f"nearestNeighbor(chunk_small_embeddings, q{i}))"
            )

        # Combine all nearestNeighbor operators with OR
        nn_clause = " OR ".join(nn_parts)

        # Base WHERE clause with collection filter and hybrid retrieval
        # - userInput uses the primary query (index 0)
        # - nearestNeighbor uses all queries (combined with OR)
        # Note: Each annotated operator wrapped in parens for YQL parsing
        where_parts = [
            f"airweave_system_metadata_collection_id contains '{airweave_collection_id}'",
            f"(({{targetHits:{self.TARGET_HITS}}}userInput(@query)) OR {nn_clause})",
        ]

        # Inject user filter if present
        if yql_filter:
            where_parts.append(f"({yql_filter})")

        # Query all entity schemas - Vespa doesn't automatically include child schemas
        # when querying parent. Use "sources *" or explicit list of all schemas.
        all_schemas = ", ".join(self._get_all_vespa_schemas())
        yql = f"select * from sources {all_schemas} where {' AND '.join(where_parts)}"
        return yql

    async def _embed_queries(self, queries: List[str]) -> tuple[List[List[float]], List[List[int]]]:
        """Pre-compute embeddings for search queries.

        Uses text-embedding-3-large model with Matryoshka truncation to get 768-dim
        embeddings, then binary-packs them for ANN search.

        Args:
            queries: List of query texts

        Returns:
            Tuple of (large_embeddings, small_embeddings) where:
            - large_embeddings: 768-dim float vectors for ranking
            - small_embeddings: 96 int8 binary-packed vectors for ANN
        """
        from airweave.platform.embedders import DenseEmbedder

        # Use default model (text-embedding-3-large) and request 768-dim via Matryoshka
        embedder = DenseEmbedder()  # Uses text-embedding-3-large (3072 native dims)
        large_embeddings = await embedder.embed_many(queries, self.logger, dimensions=768)

        # Binary pack for ANN search (same logic as VespaChunkEmbedProcessor)
        small_embeddings = [self._pack_bits_for_query(emb) for emb in large_embeddings]

        return large_embeddings, small_embeddings

    def _pack_bits_for_query(self, embedding: List[float]) -> List[int]:
        """Binary pack a query embedding for Vespa's hamming distance ANN.

        Args:
            embedding: 768-dim float embedding

        Returns:
            96 int8 values (768 bits packed into 96 bytes)
        """
        import numpy as np

        arr = np.array(embedding, dtype=np.float32)
        bits = (arr > 0).astype(np.uint8)
        packed = np.packbits(bits)
        packed_int8 = packed.astype(np.int8)
        return packed_int8.tolist()

    def _build_query_params(
        self,
        queries: List[str],
        primary_query: str,
        limit: int,
        offset: int,
        large_embeddings: List[List[float]],
        small_embeddings: List[List[int]],
    ) -> Dict[str, Any]:
        """Build Vespa query parameters with pre-computed embeddings.

        Creates embedding parameters for each query (q0, q1, q2, ...) to support
        multiple nearestNeighbor operators in the YQL.

        Args:
            queries: List of search query texts
            primary_query: The primary query (first in list)
            limit: Maximum number of results
            offset: Results to skip (pagination)
            large_embeddings: Pre-computed 768-dim embeddings (one per query)
            small_embeddings: Pre-computed binary-packed embeddings (one per query)

        Returns:
            Dict of Vespa query parameters
        """
        # Calculate effective rerank counts based on requested limit
        # Schema defaults: second-phase=200, global-phase=100
        # Override if user requests more than defaults
        effective_limit = limit + offset
        second_phase_rerank = max(200, effective_limit * 2)  # 2x buffer for global phase
        global_phase_rerank = max(100, effective_limit)  # At least what user requested

        query_params: Dict[str, Any] = {
            "query": primary_query,  # For userInput(@query) in YQL
            "ranking.profile": "hybrid-rrf",
            "hits": effective_limit,
            "presentation.summary": "full",
            # Override schema rerank-count if user needs more than 100 results
            "ranking.softtimeout.enable": "false",  # Ensure we get all results
            "ranking.rerankCount": second_phase_rerank,  # Second-phase candidates
            "ranking.globalPhase.rerankCount": global_phase_rerank,  # Final RRF output
        }

        # Primary embeddings for ranking (float_embedding for cosine similarity)
        # Note: ranking.features.query() is used for rank profile expressions
        # Use "values" format for indexed tensors (x[N]), not "cells" format (for mapped x{})
        if large_embeddings:
            query_params["ranking.features.query(float_embedding)"] = {
                "values": large_embeddings[0]
            }
            # Primary binary embedding for ranking functions (not ANN)
            query_params["ranking.features.query(embedding)"] = {"values": small_embeddings[0]}

        # Add embedding for each query (q0, q1, q2, ...) for multi-query nearestNeighbor
        # CRITICAL: nearestNeighbor operator requires input.query() format, not ranking.features
        # input.query() provides tensor values to the nearestNeighbor operator
        # ranking.features.query() provides values for rank profile expressions
        # Use "values" format for indexed tensors (tensor<int8>(x[96]))
        for i, (_large_emb, small_emb) in enumerate(
            zip(large_embeddings, small_embeddings, strict=False)
        ):
            # Binary packed embedding for ANN search (nearestNeighbor operator)
            query_params[f"input.query(q{i})"] = {"values": small_emb}

        return query_params

    def _escape_query_for_yql(self, query: str) -> str:
        """Escape a query string for safe inclusion in YQL.

        Args:
            query: Raw query string

        Returns:
            Escaped query string safe for YQL
        """
        # Escape backslashes first, then quotes
        return query.replace("\\", "\\\\").replace('"', '\\"')

    def translate_filter(self, filter: Optional[Dict[str, Any]]) -> Optional[str]:
        """Translate Airweave filter to Vespa YQL filter string.

        Converts Airweave canonical filter format to Vespa YQL WHERE clause components:
        - must conditions -> AND
        - should conditions -> OR
        - must_not conditions -> NOT (AND)
        - FieldCondition with match -> "field contains 'value'"
        - FieldCondition with range -> comparison operators

        Args:
            filter: Airweave canonical filter dict

        Returns:
            YQL filter string or None
        """
        if filter is None:
            return None

        # Filter should already be a dict, but handle Pydantic models for safety
        if hasattr(filter, "model_dump"):
            filter_dict = filter.model_dump(exclude_none=True)
        elif isinstance(filter, dict):
            filter_dict = filter
        else:
            self.logger.warning(f"[VespaSearch] Unknown filter type: {type(filter)}, ignoring")
            return None

        try:
            yql_clause = self._build_yql_clause(filter_dict)
            if yql_clause:
                self.logger.debug(f"[VespaSearch] Translated filter to YQL: {yql_clause}")
            return yql_clause
        except Exception as e:
            self.logger.warning(f"[VespaSearch] Failed to translate filter: {e}")
            return None

    def _build_yql_clause(self, filter_dict: Dict[str, Any]) -> str:
        """Build YQL WHERE clause from filter dictionary.

        Args:
            filter_dict: Qdrant-style filter dictionary

        Returns:
            YQL clause string
        """
        clauses = []

        # Handle 'must' conditions (AND)
        if "must" in filter_dict and filter_dict["must"]:
            must_clauses = [self._translate_condition(c) for c in filter_dict["must"]]
            must_clauses = [c for c in must_clauses if c]  # Filter out empty
            if must_clauses:
                clauses.append(f"({' AND '.join(must_clauses)})")

        # Handle 'should' conditions (OR)
        if "should" in filter_dict and filter_dict["should"]:
            should_clauses = [self._translate_condition(c) for c in filter_dict["should"]]
            should_clauses = [c for c in should_clauses if c]  # Filter out empty
            if should_clauses:
                clauses.append(f"({' OR '.join(should_clauses)})")

        # Handle 'must_not' conditions (NOT)
        if "must_not" in filter_dict and filter_dict["must_not"]:
            must_not_clauses = [self._translate_condition(c) for c in filter_dict["must_not"]]
            must_not_clauses = [c for c in must_not_clauses if c]  # Filter out empty
            if must_not_clauses:
                clauses.append(f"!({' AND '.join(must_not_clauses)})")

        return " AND ".join(clauses) if clauses else ""

    def translate_temporal(
        self, config: Optional[AirweaveTemporalConfig]
    ) -> Optional[Dict[str, Any]]:
        """Translate Airweave temporal config to Vespa ranking parameters.

        Note: Temporal relevance ranking is not yet implemented for Vespa.
        This method is kept for interface compatibility and future implementation.

        Args:
            config: Airweave temporal relevance configuration

        Returns:
            None - temporal relevance not yet supported for Vespa
        """
        # Temporal relevance not yet supported for Vespa
        return None

    def _map_field_name(self, key: str) -> str:
        """Map logical field names to Vespa field paths (flattened metadata fields).

        Handles multiple input formats:
        - Short names: "entity_type" -> "airweave_system_metadata_entity_type"
        - Dotted notation: "airweave_system_metadata.entity_type" -> flattened
        - Already flat: "airweave_system_metadata_entity_type" -> unchanged
        """
        meta_field_map = {
            # System metadata fields (short form)
            "collection_id": "airweave_system_metadata_collection_id",
            "entity_type": "airweave_system_metadata_entity_type",
            "sync_id": "airweave_system_metadata_sync_id",
            "sync_job_id": "airweave_system_metadata_sync_job_id",
            "content_hash": "airweave_system_metadata_hash",
            "hash": "airweave_system_metadata_hash",
            "original_entity_id": "airweave_system_metadata_original_entity_id",
            "source_name": "airweave_system_metadata_source_name",
            # Dotted notation from QueryInterpretation (Qdrant-style)
            "airweave_system_metadata.collection_id": "airweave_system_metadata_collection_id",
            "airweave_system_metadata.entity_type": "airweave_system_metadata_entity_type",
            "airweave_system_metadata.sync_id": "airweave_system_metadata_sync_id",
            "airweave_system_metadata.sync_job_id": "airweave_system_metadata_sync_job_id",
            "airweave_system_metadata.hash": "airweave_system_metadata_hash",
            "airweave_system_metadata.original_entity_id": (
                "airweave_system_metadata_original_entity_id"
            ),
            "airweave_system_metadata.source_name": "airweave_system_metadata_source_name",
            # Access control fields (dot notation -> flat field)
            "access.is_public": "access_is_public",
            "access.viewers": "access_viewers",
        }
        return meta_field_map.get(key, key)

    def _translate_condition(self, condition: Dict[str, Any]) -> str:
        """Translate a single Qdrant filter condition to YQL.

        Args:
            condition: Single condition dictionary

        Returns:
            YQL condition string
        """
        # Handle nested filter (recursive)
        if "must" in condition or "should" in condition or "must_not" in condition:
            return self._build_yql_clause(condition)

        # Handle FieldCondition with 'key' and 'match'
        if "key" in condition and "match" in condition:
            return self._translate_match_condition(condition)

        # Handle FieldCondition with 'key' and 'range'
        if "key" in condition and "range" in condition:
            return self._translate_range_condition(condition)

        # Handle HasId filter (list of IDs)
        if "has_id" in condition:
            return self._translate_has_id_condition(condition)

        # Handle is_null check (for mixed collection access control)
        if "key" in condition and "is_null" in condition:
            return self._translate_is_null_condition(condition)

        # Fallback - return empty (will be filtered out)
        self.logger.debug(f"[VespaSearch] Unknown condition type: {condition}")
        return ""

    def _translate_match_condition(self, condition: Dict[str, Any]) -> str:
        """Translate a match condition to YQL.

        Handles various match types:
        - {"value": "x"} -> simple equality/contains
        - {"any": ["a", "b"]} -> OR across array values (for access control filtering)
        - Direct value -> simple equality/contains
        """
        key = self._map_field_name(condition["key"])
        match = condition["match"]

        # Handle "any" operator for array fields (access control filtering)
        # Example: {"key": "access.viewers", "match": {"any": ["user:a@x.com", "group:sp:1"]}}
        # Generates: (access_viewers contains "user:a@x.com" OR ...)
        if isinstance(match, dict) and "any" in match:
            values = match["any"]
            if not values:
                return "false"  # No principals = no access
            clauses = [f'{key} contains "{self._escape_yql_value(v)}"' for v in values]
            return f"({' OR '.join(clauses)})"

        # Handle simple value match
        value = match.get("value", "") if isinstance(match, dict) else match

        if isinstance(value, str):
            escaped_value = self._escape_yql_value(value)
            return f'{key} contains "{escaped_value}"'
        elif isinstance(value, bool):
            return f"{key} = {str(value).lower()}"
        elif isinstance(value, (int, float)):
            return f"{key} = {value}"
        return f'{key} contains "{value}"'

    def _escape_yql_value(self, value: str) -> str:
        """Escape special characters for YQL string literals.

        Args:
            value: Raw string value

        Returns:
            Escaped string safe for YQL
        """
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _translate_is_null_condition(self, condition: Dict[str, Any]) -> str:
        """Translate is_null condition to YQL.

        Used for mixed collection access control: entities from non-AC sources
        don't have access fields, so we need to check if the field is null/absent.

        Args:
            condition: Condition with "key" and "is_null" fields

        Returns:
            YQL condition string: "isNull(field)" or "!isNull(field)"
        """
        key = self._map_field_name(condition["key"])
        is_null = condition["is_null"]

        if is_null:
            return f"isNull({key})"
        else:
            return f"!isNull({key})"

    def _translate_range_condition(self, condition: Dict[str, Any]) -> str:
        """Translate a range condition to YQL.

        Handles datetime conversion for created_at/updated_at fields which are
        stored as epoch milliseconds in Vespa but may come as ISO strings from
        QueryInterpretation.
        """
        key = self._map_field_name(condition["key"])
        range_cond = condition["range"]
        parts = []

        # Fields that are stored as epoch milliseconds in Vespa
        epoch_ms_fields = {"created_at", "updated_at"}

        for op, symbol in [("gt", ">"), ("gte", ">="), ("lt", "<"), ("lte", "<=")]:
            if op in range_cond:
                value = range_cond[op]
                # Convert ISO datetime strings to epoch milliseconds for date fields
                if key in epoch_ms_fields and isinstance(value, str):
                    value = self._parse_datetime_to_epoch_ms(value)
                parts.append(f"{key} {symbol} {value}")

        return " AND ".join(parts) if parts else ""

    def _parse_datetime_to_epoch_ms(self, value: str) -> int:
        """Parse ISO datetime string to epoch milliseconds.

        Args:
            value: ISO format datetime string (e.g., "2025-12-01T00:00:00Z")

        Returns:
            Epoch milliseconds as integer
        """
        from datetime import datetime

        try:
            # Handle ISO format with Z suffix
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            dt = datetime.fromisoformat(value)
            return int(dt.timestamp() * 1000)
        except (ValueError, AttributeError) as e:
            self.logger.warning(f"[VespaSearch] Failed to parse datetime '{value}': {e}")
            # Return the original value if parsing fails
            return value

    def _translate_has_id_condition(self, condition: Dict[str, Any]) -> str:
        """Translate a has_id condition to YQL."""
        ids = condition["has_id"]
        if ids:
            id_clauses = [f'entity_id contains "{id}"' for id in ids]
            return f"({' OR '.join(id_clauses)})"
        return ""

    def _convert_vespa_results(self, response: Any) -> List[SearchResult]:
        results = []
        for i, hit in enumerate(response.hits or []):
            fields = hit.get("fields", {})

            # Debug: Log first few results with their field keys
            if i < 3:
                self.logger.debug(
                    f"[VespaSearch] Hit {i}: id={hit.get('id', 'N/A')}, "
                    f"relevance={hit.get('relevance', 0.0):.4f}, "
                    f"field_keys={list(fields.keys())[:15]}..."
                )

            # Just use all fields as payload, extracting id and score
            result = SearchResult(
                id=hit.get("id", ""),
                score=hit.get("relevance", 0.0),
                payload=fields,  # Pass through all Vespa fields
            )
            results.append(result)

        # Summary log
        if results:
            first_payload = results[0].payload
            self.logger.info(
                f"[VespaSearch] Result sample - Available fields: {list(first_payload.keys())}"
            )

        return results

    async def get_vector_config_names(self) -> list[str]:
        """Get vector config names.

        Returns:
            List of vector field names configured in Vespa schema
        """
        return ["chunk_small_embeddings", "chunk_large_embeddings"]

    async def close_connection(self) -> None:
        """Close the Vespa connection."""
        if self.app:
            self.logger.debug("Closing Vespa connection")
            self.app = None
