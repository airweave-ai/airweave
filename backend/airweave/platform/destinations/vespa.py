"""Vespa destination implementation.

Vespa handles chunking and embedding internally via schema definition,
so this destination only transforms entities and feeds them to Vespa.

IMPORTANT: pyvespa methods are synchronous and would block the event loop.
All pyvespa calls are wrapped in asyncio.to_thread() to maintain concurrency.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

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
    requires_client_embedding=False,
    supports_temporal_relevance=False,
)
class VespaDestination(VectorDBDestination):
    """Vespa destination - Vespa handles chunking/embedding internally."""

    # Vespa embeds server-side, only needs text extraction
    from airweave.platform.destinations._base import ProcessingRequirement

    processing_requirement = ProcessingRequirement.TEXT_ONLY

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
        # Get entity type from metadata or class name
        entity_type = (
            entity.airweave_system_metadata.entity_type
            if entity.airweave_system_metadata and entity.airweave_system_metadata.entity_type
            else entity.__class__.__name__
        )

        # Determine the Vespa schema for this entity
        schema = self._get_vespa_schema(entity)

        # Composite document ID: entity_type + entity_id for uniqueness
        doc_id = f"{entity_type}_{entity.entity_id}"

        # Build fields dict with base entity fields
        fields = {
            "entity_id": entity.entity_id,
            "name": entity.name,
        }

        # Breadcrumbs (array of struct)
        if entity.breadcrumbs:
            fields["breadcrumbs"] = [b.model_dump() for b in entity.breadcrumbs]

        # Timestamps as epoch seconds (Vespa expects long)
        if entity.created_at:
            fields["created_at"] = int(entity.created_at.timestamp())
        if entity.updated_at:
            fields["updated_at"] = int(entity.updated_at.timestamp())

        # Textual representation - this is what Vespa chunks and embeds
        if entity.textual_representation:
            fields["textual_representation"] = entity.textual_representation

        # System metadata (struct) mirrors AirweaveSystemMetadata
        meta_fields: dict[str, Any] = {}

        # Derived from sync context (not part of AirweaveSystemMetadata)
        if self.collection_id:
            meta_fields["collection_id"] = str(self.collection_id)

        if entity.airweave_system_metadata:
            meta = entity.airweave_system_metadata
            if meta.entity_type:
                meta_fields["entity_type"] = meta.entity_type
            if meta.sync_id:
                meta_fields["sync_id"] = str(meta.sync_id)
            if meta.sync_job_id:
                meta_fields["sync_job_id"] = str(meta.sync_job_id)
            if meta.hash:
                meta_fields["hash"] = meta.hash
            if meta.chunk_index is not None:
                meta_fields["chunk_index"] = meta.chunk_index
            if meta.original_entity_id:
                meta_fields["original_entity_id"] = meta.original_entity_id
            if meta.source_name:
                meta_fields["source_name"] = meta.source_name
            if meta.db_entity_id:
                meta_fields["db_entity_id"] = str(meta.db_entity_id)
            if meta.db_created_at:
                meta_fields["db_created_at"] = int(meta.db_created_at.timestamp())
            if meta.db_updated_at:
                meta_fields["db_updated_at"] = int(meta.db_updated_at.timestamp())

        # Ensure critical metadata is always present
        if "entity_type" not in meta_fields:
            meta_fields["entity_type"] = entity_type
        if "original_entity_id" not in meta_fields and entity.entity_id:
            meta_fields["original_entity_id"] = entity.entity_id

        # Drop None values and attach to fields
        meta_fields = {k: v for k, v in meta_fields.items() if v is not None}
        if meta_fields:
            fields["airweave_system_metadata"] = meta_fields

        # Add web-specific fields if this is a WebEntity
        if isinstance(entity, WebEntity):
            fields["crawl_url"] = entity.crawl_url

        # Add file-specific fields if this is a FileEntity
        if isinstance(entity, FileEntity):
            fields["url"] = entity.url
            fields["size"] = entity.size
            fields["file_type"] = entity.file_type
            if entity.mime_type:
                fields["mime_type"] = entity.mime_type
            if entity.local_path:
                fields["local_path"] = entity.local_path

        # Add code-specific fields if this is a CodeFileEntity
        if isinstance(entity, CodeFileEntity):
            fields["repo_name"] = entity.repo_name
            fields["path_in_repo"] = entity.path_in_repo
            fields["repo_owner"] = entity.repo_owner
            fields["language"] = entity.language
            fields["commit_id"] = entity.commit_id

        # Extract extra fields into payload JSON
        # Use dynamic field derivation so entity class definitions are the single source of truth
        schema_fields = _get_schema_fields_for_entity(entity)
        entity_dict = entity.model_dump(mode="json")
        payload = {k: v for k, v in entity_dict.items() if k not in schema_fields}
        if payload:
            fields["payload"] = json.dumps(payload)

        # Remove None values from top-level fields
        fields = {k: v for k, v in fields.items() if v is not None}

        return schema, {
            "id": doc_id,
            "fields": fields,
        }

    async def setup_collection(self, vector_size: int | None = None) -> None:
        """Set up collection in Vespa.

        Note: Vespa schema is deployed separately via vespa-deploy.
        This method is a no-op but kept for interface compatibility.
        """
        self.logger.debug("Vespa schema is managed via vespa-deploy, skipping setup_collection")

    async def bulk_insert(self, entities: list[BaseEntity]) -> None:
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

        self.logger.info(f"Feeding {len(entities)} entities to Vespa (batch)")

        # Transform all entities to Vespa format, grouped by schema
        docs_by_schema: dict[str, list[dict]] = defaultdict(list)
        for entity in entities:
            try:
                schema, vespa_doc = self._transform_entity(entity)
                docs_by_schema[schema].append(vespa_doc)
            except Exception as e:
                self.logger.error(f"Failed to transform entity {entity.entity_id}: {e}")

        total_docs = sum(len(docs) for docs in docs_by_schema.values())
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
        for schema, docs in docs_by_schema.items():
            self.logger.debug(f"Feeding {len(docs)} documents to schema '{schema}'")
            await asyncio.to_thread(_feed_schema_sync, schema, docs)

        self.logger.info(f"Vespa feed complete: {success_count} success, {len(failed_docs)} failed")

        if failed_docs:
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
        """Delete all documents from a sync run.

        Args:
            sync_id: The sync ID to delete documents for
        """
        if not self.app:
            raise RuntimeError("Vespa client not initialized")

        # Search across all schemas
        for schema in self._get_all_vespa_schemas():
            yql = (
                f"select documentid from {schema} where "
                f"airweave_system_metadata.sync_id contains '{sync_id}' and "
                f"airweave_system_metadata.collection_id contains '{self.collection_id}'"
            )
            await self._delete_by_query(yql, schema)

    async def delete_by_collection_id(self, collection_id: UUID) -> None:
        """Delete all documents for a collection.

        Used when deleting an entire collection.

        Args:
            collection_id: The collection ID to delete documents for
        """
        if not self.app:
            raise RuntimeError("Vespa client not initialized")

        # Search across all schemas
        for schema in self._get_all_vespa_schemas():
            yql = (
                f"select documentid from {schema} where "
                f"airweave_system_metadata.collection_id contains '{collection_id}'"
            )
            await self._delete_by_query(yql, schema)

    async def bulk_delete_by_parent_ids(self, parent_ids: list[str], sync_id: UUID) -> None:
        """Delete all documents for multiple parent IDs.

        Args:
            parent_ids: List of parent entity IDs
            sync_id: The sync ID for scoping
        """
        if not parent_ids or not self.app:
            return

        # Delete each parent's documents from all schemas
        for parent_id in parent_ids:
            for schema in self._get_all_vespa_schemas():
                yql = (
                    f"select documentid from {schema} where "
                    f"airweave_system_metadata.original_entity_id contains '{parent_id}' and "
                    f"airweave_system_metadata.collection_id contains '{self.collection_id}'"
                )
                await self._delete_by_query(yql, schema)

    async def _delete_by_query(self, yql: str, schema: str) -> None:
        """Execute a delete operation based on a YQL query with pagination.

        IMPORTANT: pyvespa query() and delete_data() are synchronous,
        so we run them in a thread pool to avoid blocking the event loop.

        Uses pagination to handle large result sets that may exceed Vespa's
        configured max hits limit.

        Args:
            yql: YQL query to find documents to delete
            schema: The Vespa schema to delete from
        """
        if not self.app:
            return

        batch_size = 400  # Vespa's default maxHits limit
        total_deleted = 0

        try:
            # Paginate through all matching documents
            while True:
                # Run synchronous query in thread pool
                response = await asyncio.to_thread(self.app.query, yql=yql, hits=batch_size)

                if not response.is_successful():
                    self.logger.error(f"Error during delete operation: {response.json}")
                    return

                hits = response.hits or []
                if not hits:
                    if total_deleted > 0:
                        self.logger.info(
                            f"Deleted {total_deleted} total documents from Vespa schema '{schema}'"
                        )
                    else:
                        self.logger.debug(f"No documents found to delete from {schema}")
                    return

                self.logger.debug(
                    f"Deleting batch of {len(hits)} documents from Vespa schema '{schema}'"
                )

                # Collect document IDs to delete
                doc_ids_to_delete = []
                for hit in hits:
                    doc_id = hit.get("id", "")
                    if doc_id:
                        # Extract the user-specified ID from the full document ID
                        # Format: id:namespace:doctype::user_id
                        parts = doc_id.split("::")
                        if len(parts) >= 2:
                            doc_ids_to_delete.append(parts[-1])

                # Define synchronous delete operation for batch
                # Use default arg to bind loop variable (avoids late binding issues)
                def _delete_batch_sync(ids: list = doc_ids_to_delete) -> int:
                    deleted = 0
                    for user_id in ids:
                        delete_response = self.app.delete_data(
                            schema=schema,
                            data_id=user_id,
                            namespace="airweave",
                        )
                        if delete_response.is_successful():
                            deleted += 1
                    return deleted

                # Run synchronous deletes in thread pool
                deleted = await asyncio.to_thread(_delete_batch_sync)
                total_deleted += deleted

                # If we got fewer hits than batch_size, we're done
                if len(hits) < batch_size:
                    if total_deleted > 0:
                        self.logger.info(
                            f"Deleted {total_deleted} total documents from Vespa schema '{schema}'"
                        )
                    break

        except Exception as e:
            self.logger.error(f"Error during delete operation: {e}")

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

        Vespa handles embedding generation server-side, so dense_embeddings is ignored.
        YQL is built at runtime with proper filter injection into WHERE clause.

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
            dense_embeddings: Ignored - Vespa embeds server-side
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

        # Translate filter to YQL clause (if present)
        yql_filter = self.translate_filter(filter) if filter else None

        # Build YQL with proper filter injection and multi-query support
        yql = self._build_search_yql(queries, airweave_collection_id, yql_filter)

        # Build query parameters with embeddings for all queries
        query_params = self._build_query_params(queries, primary_query, limit, offset)
        query_params["yql"] = yql

        self.logger.debug(f"[VespaSearch] YQL: {yql}")

        # Execute query in thread pool (pyvespa is synchronous)
        try:
            response = await asyncio.to_thread(self.app.query, body=query_params)
        except Exception as e:
            self.logger.error(f"[VespaSearch] Vespa query failed: {e}")
            raise RuntimeError(f"Vespa search failed: {e}") from e

        # Check for errors
        if not response.is_successful():
            error_msg = getattr(response, "json", {}).get("error", str(response))
            self.logger.error(f"[VespaSearch] Vespa returned error: {error_msg}")
            raise RuntimeError(f"Vespa search error: {error_msg}")

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
        nn_parts = []
        for i in range(len(queries)):
            # Use label annotation to distinguish closeness from different queries
            nn_parts.append(
                f'{{label:"q{i}", targetHits:{self.TARGET_HITS}}}'
                f"nearestNeighbor(chunk_small_embeddings, q{i})"
            )

        # Combine all nearestNeighbor operators with OR
        nn_clause = " OR ".join(nn_parts)

        # Base WHERE clause with collection filter and hybrid retrieval
        # - userInput uses the primary query (index 0)
        # - nearestNeighbor uses all queries (combined with OR)
        where_parts = [
            f"airweave_system_metadata.collection_id contains '{airweave_collection_id}'",
            f"({{targetHits:{self.TARGET_HITS}}}userInput(@query) OR {nn_clause})",
        ]

        # Inject user filter if present
        if yql_filter:
            where_parts.append(f"({yql_filter})")

        yql = f"select * from base_entity where {' AND '.join(where_parts)}"
        return yql

    def _build_query_params(
        self,
        queries: List[str],
        primary_query: str,
        limit: int,
        offset: int,
    ) -> Dict[str, Any]:
        """Build Vespa query parameters with embeddings for all queries.

        Creates embedding parameters for each query (q0, q1, q2, ...) to support
        multiple nearestNeighbor operators in the YQL.

        Args:
            queries: List of search query texts
            primary_query: The primary query (first in list)
            limit: Maximum number of results
            offset: Results to skip (pagination)

        Returns:
            Dict of Vespa query parameters
        """
        escaped_primary = self._escape_query_for_yql(primary_query)

        query_params: Dict[str, Any] = {
            "query": primary_query,  # For userInput(@query) in YQL
            "ranking.profile": "hybrid-rrf",
            "hits": limit + offset,
            "presentation.summary": "full",
            # Keep legacy embedding params for backward compatibility with rank profile
            "ranking.features.query(embedding)": f'embed(nomicmb, "{escaped_primary}")',
            "ranking.features.query(float_embedding)": f'embed(nomicmb, "{escaped_primary}")',
        }

        # Add embedding for each query (q0, q1, q2, ...)
        for i, q in enumerate(queries):
            escaped_q = self._escape_query_for_yql(q)
            query_params[f"ranking.features.query(q{i})"] = f'embed(nomicmb, "{escaped_q}")'

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
        """Map logical field names to Vespa field paths (handles nested structs)."""
        meta_field_map = {
            "collection_id": "airweave_system_metadata.collection_id",
            "entity_type": "airweave_system_metadata.entity_type",
            "sync_id": "airweave_system_metadata.sync_id",
            "sync_job_id": "airweave_system_metadata.sync_job_id",
            "content_hash": "airweave_system_metadata.hash",
            "hash": "airweave_system_metadata.hash",
            "original_entity_id": "airweave_system_metadata.original_entity_id",
            "source_name": "airweave_system_metadata.source_name",
            "db_entity_id": "airweave_system_metadata.db_entity_id",
            "db_created_at": "airweave_system_metadata.db_created_at",
            "db_updated_at": "airweave_system_metadata.db_updated_at",
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
            key = self._map_field_name(condition["key"])
            match = condition["match"]

            if isinstance(match, dict):
                value = match.get("value", "")
            else:
                value = match

            # Escape quotes in value
            if isinstance(value, str):
                escaped_value = value.replace('"', '\\"')
                return f'{key} contains "{escaped_value}"'
            elif isinstance(value, bool):
                return f"{key} = {str(value).lower()}"
            elif isinstance(value, (int, float)):
                return f"{key} = {value}"
            else:
                return f'{key} contains "{value}"'

        # Handle FieldCondition with 'key' and 'range'
        if "key" in condition and "range" in condition:
            key = self._map_field_name(condition["key"])
            range_cond = condition["range"]
            parts = []

            if "gt" in range_cond:
                parts.append(f"{key} > {range_cond['gt']}")
            if "gte" in range_cond:
                parts.append(f"{key} >= {range_cond['gte']}")
            if "lt" in range_cond:
                parts.append(f"{key} < {range_cond['lt']}")
            if "lte" in range_cond:
                parts.append(f"{key} <= {range_cond['lte']}")

            return " AND ".join(parts) if parts else ""

        # Handle HasId filter (list of IDs)
        if "has_id" in condition:
            ids = condition["has_id"]
            if ids:
                id_clauses = [f'entity_id contains "{id}"' for id in ids]
                return f"({' OR '.join(id_clauses)})"
            return ""

        # Fallback - return empty (will be filtered out)
        self.logger.debug(f"[VespaSearch] Unknown condition type: {condition}")
        return ""

    def _convert_vespa_results(self, response: Any) -> List[SearchResult]:
        results = []
        for hit in response.hits or []:
            fields = hit.get("fields", {})
            # Just use all fields as payload, extracting id and score
            result = SearchResult(
                id=hit.get("id", ""),
                score=hit.get("relevance", 0.0),
                payload=fields,  # Pass through all Vespa fields
            )
            results.append(result)
        return results

    async def has_keyword_index(self) -> bool:
        """Check if Vespa has keyword index.

        Returns:
            True - Vespa always has BM25 via schema configuration
        """
        return True

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
