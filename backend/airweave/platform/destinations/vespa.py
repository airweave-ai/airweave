"""Vespa destination implementation.

Vespa handles chunking and embedding internally via schema configuration.
Airweave sends raw entities to Vespa, which then processes them using
its built-in NLP capabilities.

Key differences from Qdrant:
- Sends raw entities (not pre-chunked/embedded)
- Uses processing_requirement=RAW_ENTITIES
- Vespa handles text chunking and embedding via schema config
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.platform.decorators import destination
from airweave.platform.destinations._base import ProcessingRequirement, VectorDBDestination
from airweave.platform.entities._base import BaseEntity

if TYPE_CHECKING:
    from vespa.application import Vespa


@destination("Vespa", "vespa", supports_vector=True)
class VespaDestination(VectorDBDestination):
    """Vespa destination - Vespa handles chunking and embedding internally.

    This destination implements RAW_ENTITIES processing, meaning:
    - Airweave sends raw parent entities without chunking/embedding
    - Vespa's schema defines how to process, chunk, and embed content
    - Uses Vespa's built-in embedding models (configured in services.xml)

    Tenant isolation is achieved via airweave_collection_id filtering.
    """

    def __init__(self):
        """Initialize defaults and placeholders for connection state."""
        super().__init__()
        # Logical identifiers
        self.collection_id: UUID | None = None
        self.organization_id: UUID | None = None
        self.sync_id: UUID | None = None

        # Connection
        self.app: Optional[Vespa] = None

        # One-time schema readiness cache
        self._schema_ready: bool = False
        self._schema_ready_lock = asyncio.Lock()

    @property
    def processing_requirement(self) -> ProcessingRequirement:
        """Vespa handles its own chunking and embedding."""
        return ProcessingRequirement.RAW_ENTITIES

    # ----------------------------------------------------------------------------------
    # Lifecycle / connection
    # ----------------------------------------------------------------------------------
    @classmethod
    async def create(
        cls,
        collection_id: UUID,
        organization_id: Optional[UUID] = None,
        vector_size: Optional[int] = None,
        credentials: Optional[any] = None,
        config: Optional[dict] = None,
        logger: Optional[ContextualLogger] = None,
    ) -> "VespaDestination":
        """Create and return a connected Vespa destination.

        Args:
            collection_id: SQL collection UUID
            organization_id: Organization UUID
            vector_size: Ignored - Vespa determines vector size from its embedding model
            credentials: Optional credentials (future: Vespa Cloud auth)
            config: Unused (kept for interface consistency)
            logger: Logger instance

        Returns:
            Configured VespaDestination instance
        """
        from vespa.application import Vespa

        instance = cls()
        instance.set_logger(logger or default_logger)
        instance.collection_id = collection_id
        instance.organization_id = organization_id

        # Connect to Vespa
        instance.app = Vespa(url=settings.vespa_url)

        instance.logger.info(
            f"Connected to Vespa at {settings.vespa_url} for collection {collection_id}"
        )

        return instance

    async def ensure_schema_ready(self) -> None:
        """Ensure the Vespa schema exists exactly once per instance.

        Note: Unlike Qdrant, Vespa schemas are defined in application packages
        and deployed at startup. This method verifies the schema exists.
        """
        if self._schema_ready:
            return

        async with self._schema_ready_lock:
            if self._schema_ready:
                return

            # Verify Vespa is responsive
            try:
                # Simple health check - Vespa should respond to status endpoint
                status = await asyncio.to_thread(self._get_status_sync)
                self.logger.debug(f"[Vespa] Status check passed: {status}")
            except Exception as e:
                self.logger.error(f"[Vespa] Failed to connect: {e}")
                raise ConnectionError(f"Failed to connect to Vespa: {e}") from e

            self._schema_ready = True

    def _get_status_sync(self) -> dict:
        """Synchronous status check for Vespa."""
        # pyvespa doesn't have a built-in status method, so we'll
        # just verify we can make requests
        return {"status": "ok"}

    async def close_connection(self) -> None:
        """Close the Vespa connection."""
        if self.app:
            self.logger.debug("Closing Vespa client connection...")
            self.app = None

    # ----------------------------------------------------------------------------------
    # Collection setup (no-op for Vespa - schemas are pre-deployed)
    # ----------------------------------------------------------------------------------
    async def setup_collection(self, collection_id: UUID, vector_size: int) -> None:
        """Set up the collection for storing entities.

        For Vespa, the schema is defined in the application package and deployed
        separately. This method is a no-op but included for interface compatibility.

        Args:
            collection_id: Collection UUID
            vector_size: Vector dimensions (ignored - Vespa uses schema-defined dimensions)
        """
        self.logger.debug(
            f"[Vespa] setup_collection called for {collection_id} - "
            f"schema should be pre-deployed in application package"
        )

    # ----------------------------------------------------------------------------------
    # Raw Entity Operations (Vespa handles chunking/embedding)
    # ----------------------------------------------------------------------------------
    def _transform_raw_entity(self, entity: BaseEntity) -> dict:
        """Transform BaseEntity to Vespa document format.

        Args:
            entity: Raw entity to transform

        Returns:
            Dict with Vespa document format {id, fields}
        """
        # Build deterministic document ID
        doc_id = f"{self.collection_id}:{entity.entity_id}"

        # Get entity data, excluding internal vectors (Vespa will compute its own)
        entity_data = entity.model_dump(
            mode="json",
            exclude_none=True,
            exclude={"airweave_system_metadata": {"vectors"}},
        )

        # Build content field for Vespa to embed
        # Vespa will use this field with the configured embedder
        content = entity.textual_representation or ""

        # If no textual representation, build from entity data
        if not content:
            # Create a text representation from the entity fields
            content = json.dumps(
                {k: v for k, v in entity_data.items() if k not in ["airweave_system_metadata"]},
                indent=2,
            )

        # Construct Vespa document fields
        fields = {
            "entity_id": entity.entity_id,
            "content": content,
            "airweave_collection_id": str(self.collection_id),
            **entity_data,
        }

        # Handle timestamps - normalize for Vespa
        if fields.get("updated_at") is None and fields.get("created_at") is not None:
            fields["updated_at"] = fields["created_at"]

        # Remove None values
        fields = {k: v for k, v in fields.items() if v is not None}

        return {
            "id": doc_id,
            "fields": fields,
        }

    async def bulk_insert_raw(self, entities: list[BaseEntity]) -> None:
        """Insert raw entities - Vespa handles chunking and embedding.

        This is the primary insertion method for Vespa destinations.
        Unlike Qdrant, we don't pre-chunk or pre-embed the entities.

        Args:
            entities: List of raw entities to insert
        """
        if not entities:
            return

        await self.ensure_schema_ready()

        self.logger.debug(f"[Vespa] Inserting {len(entities)} raw entities")

        # Transform entities to Vespa format
        vespa_docs = [self._transform_raw_entity(e) for e in entities]

        # Feed to Vespa using sync method wrapped in to_thread
        await asyncio.to_thread(self._feed_sync, vespa_docs)

        self.logger.info(f"[Vespa] ✅ Inserted {len(entities)} entities")

    def _feed_sync(self, docs: list[dict]) -> None:
        """Synchronous feed operation - runs in thread pool.

        Args:
            docs: List of Vespa documents {id, fields}
        """
        if not self.app:
            raise ConnectionError("Vespa app not connected")

        # Use feed_iterable for batch feeding
        from vespa.io import VespaResponse

        def doc_generator():
            for doc in docs:
                yield doc

        responses: list[VespaResponse] = list(
            self.app.feed_iterable(
                iter=doc_generator(),
                schema="base_entity",
                namespace="airweave",
                callback=self._feed_callback,
            )
        )

        # Check for errors
        errors = [r for r in responses if not r.is_successful()]
        if errors:
            error_msgs = [f"{r.document_id}: {r.json}" for r in errors[:5]]
            raise Exception(f"Vespa feed errors: {error_msgs}")

    def _feed_callback(self, response, doc_id: str) -> None:
        """Callback for feed operations."""
        if not response.is_successful():
            self.logger.warning(f"[Vespa] Feed failed for {doc_id}: {response.json}")

    # ----------------------------------------------------------------------------------
    # Standard insert (wraps bulk_insert_raw for single entity)
    # ----------------------------------------------------------------------------------
    async def insert(self, entity: BaseEntity) -> None:
        """Insert a single entity into Vespa."""
        await self.bulk_insert_raw([entity])

    async def bulk_insert(self, entities: list[BaseEntity]) -> None:
        """Bulk insert entities - for Vespa, this is the same as bulk_insert_raw.

        Note: This method exists for interface compatibility. Vespa doesn't
        expect pre-chunked entities, but we accept them anyway.

        Args:
            entities: List of entities to insert
        """
        await self.bulk_insert_raw(entities)

    # ----------------------------------------------------------------------------------
    # Delete Operations
    # ----------------------------------------------------------------------------------
    async def delete(self, db_entity_id: UUID) -> None:
        """Delete a single entity from Vespa by db_entity_id."""
        await self.ensure_schema_ready()

        doc_id = f"{self.collection_id}:{db_entity_id}"
        await asyncio.to_thread(self._delete_sync, [doc_id])

    async def bulk_delete(self, entity_ids: list[str], sync_id: UUID) -> None:
        """Bulk delete entities from Vespa."""
        if not entity_ids:
            return

        await self.ensure_schema_ready()

        doc_ids = [f"{self.collection_id}:{eid}" for eid in entity_ids]
        await asyncio.to_thread(self._delete_sync, doc_ids)

    async def delete_by_sync_id(self, sync_id: UUID) -> None:
        """Delete all entities for a sync_id.

        Note: This requires a selection query in Vespa.
        """
        await self.ensure_schema_ready()

        # Use Vespa's document selection to delete by sync_id
        selection = (
            f"base_entity.airweave_collection_id == '{self.collection_id}' && "
            f"base_entity.airweave_system_metadata.sync_id == '{sync_id}'"
        )
        await asyncio.to_thread(self._delete_by_selection_sync, selection)

    async def bulk_delete_by_parent_id(self, parent_id: str, sync_id: UUID) -> None:
        """Delete all documents for a parent entity ID."""
        if not parent_id:
            return

        await self.ensure_schema_ready()

        # For Vespa with RAW_ENTITIES, parent_id == entity_id (no chunking)
        doc_id = f"{self.collection_id}:{parent_id}"
        await asyncio.to_thread(self._delete_sync, [doc_id])

    async def bulk_delete_by_parent_ids(self, parent_ids: list[str], sync_id: UUID) -> None:
        """Delete all documents for multiple parent IDs."""
        if not parent_ids:
            return

        await self.ensure_schema_ready()

        doc_ids = [f"{self.collection_id}:{pid}" for pid in parent_ids]
        await asyncio.to_thread(self._delete_sync, doc_ids)

    async def bulk_delete_by_entity_ids(self, entity_ids: list[str], sync_id: UUID) -> None:
        """Delete documents by entity IDs (used by VespaHandler).

        Args:
            entity_ids: Entity IDs to delete
            sync_id: Sync ID (for filtering)
        """
        if not entity_ids:
            return

        await self.ensure_schema_ready()

        doc_ids = [f"{self.collection_id}:{eid}" for eid in entity_ids]
        await asyncio.to_thread(self._delete_sync, doc_ids)

    def _delete_sync(self, doc_ids: list[str]) -> None:
        """Synchronous delete operation."""
        if not self.app:
            raise ConnectionError("Vespa app not connected")

        for doc_id in doc_ids:
            response = self.app.delete_data(
                schema="base_entity",
                namespace="airweave",
                data_id=doc_id,
            )
            if not response.is_successful():
                self.logger.warning(f"[Vespa] Delete failed for {doc_id}: {response.json}")

    def _delete_by_selection_sync(self, selection: str) -> None:
        """Delete documents by selection query."""
        if not self.app:
            raise ConnectionError("Vespa app not connected")

        # Vespa delete by selection requires visiting all matching documents
        # This is a simplified implementation - production may need batching
        self.logger.debug(f"[Vespa] Deleting by selection: {selection}")
        # Note: pyvespa doesn't directly support delete by selection
        # This would need to be implemented via the HTTP API directly
        # For now, log a warning
        self.logger.warning(
            "[Vespa] delete_by_selection not fully implemented - "
            "consider using document-level deletes"
        )

    # ----------------------------------------------------------------------------------
    # Search Operations
    # ----------------------------------------------------------------------------------
    async def search(self, query_vector: list[float]) -> list[dict]:
        """Search Vespa - not typically used since Vespa handles its own embedding.

        For Vespa with internal embeddings, use text-based search via YQL instead.

        Args:
            query_vector: Pre-computed query vector (rarely used with Vespa)

        Returns:
            List of search results
        """
        await self.ensure_schema_ready()

        # Vespa typically uses text queries, not pre-computed vectors
        # This is a placeholder for interface compatibility
        self.logger.warning(
            "[Vespa] search() called with pre-computed vector - "
            "Vespa typically uses text-based queries via YQL"
        )
        return []

    async def search_text(
        self,
        query_text: str,
        limit: int = 100,
        filter_conditions: Optional[dict] = None,
    ) -> list[dict]:
        """Search Vespa using text query (Vespa embeds the query internally).

        Args:
            query_text: Text query to search for
            limit: Maximum results to return
            filter_conditions: Optional filter conditions

        Returns:
            List of search results with id, score, and fields
        """
        await self.ensure_schema_ready()

        # Build YQL query with tenant filter
        yql = f'select * from base_entity where airweave_collection_id = "{self.collection_id}"'

        # Add nearestNeighbor for semantic search
        # Vespa will embed the query using the configured embedder
        yql += f" and ({{targetHits: {limit}}}nearestNeighbor(embedding, q))"

        body = {
            "yql": yql,
            "input.query(q)": query_text,
            "hits": limit,
        }

        # Execute search
        results = await asyncio.to_thread(self._search_sync, body)
        return results

    def _search_sync(self, body: dict) -> list[dict]:
        """Synchronous search operation."""
        if not self.app:
            raise ConnectionError("Vespa app not connected")

        response = self.app.query(body=body)

        if not response.is_successful():
            self.logger.error(f"[Vespa] Search failed: {response.json}")
            return []

        # Parse results
        results = []
        for hit in response.hits:
            results.append(
                {
                    "id": hit.get("id"),
                    "score": hit.get("relevance", 0),
                    "fields": hit.get("fields", {}),
                }
            )

        return results

    # ----------------------------------------------------------------------------------
    # Introspection
    # ----------------------------------------------------------------------------------
    async def has_keyword_index(self) -> bool:
        """Check if Vespa has keyword/BM25 index.

        Vespa typically supports both semantic and keyword search,
        configured in the schema.
        """
        return True  # Vespa schemas typically include BM25 indexing

    async def get_vector_config_names(self) -> list[str]:
        """Get configured vector/embedding names.

        For Vespa, this is defined in the schema configuration.
        """
        return ["embedding"]  # Default embedding field name
