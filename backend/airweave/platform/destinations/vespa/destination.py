"""Vespa destination - public API for Vespa operations.

This module provides the VespaDestination class which serves as the public API
for all Vespa operations. It orchestrates the lower-level components:

- VespaClient: Low-level I/O operations
- EntityTransformer: Entity to document transformation
- QueryBuilder: YQL query construction
- FilterTranslator: Filter conversion

This follows Clean Architecture principles - the destination is a thin
orchestration layer that delegates to domain-specific components.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from uuid import UUID

from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.platform.decorators import destination
from airweave.platform.destinations._base import VectorDBDestination
from airweave.platform.destinations.vespa.client import VespaClient
from airweave.platform.destinations.vespa.query_builder import QueryBuilder
from airweave.platform.destinations.vespa.transformer import EntityTransformer
from airweave.platform.entities._base import BaseEntity
from airweave.schemas.search import AirweaveTemporalConfig
from airweave.schemas.search_result import AirweaveSearchResult


@destination(
    "Vespa",
    "vespa",
    supports_vector=True,
    requires_client_embedding=True,
    supports_temporal_relevance=False,
)
class VespaDestination(VectorDBDestination):
    """Vespa destination with chunk-as-document model.

    This is the public API for Vespa operations. It provides:
    - bulk_insert: Feed entities to Vespa
    - search: Execute hybrid search queries
    - delete_by_sync_id: Delete documents for a sync run
    - delete_by_collection_id: Delete all documents for a collection
    - bulk_delete_by_parent_ids: Delete documents by parent entity IDs

    Internally, it delegates to:
    - VespaClient for I/O operations
    - EntityTransformer for entity → document conversion
    - QueryBuilder for YQL construction
    """

    from airweave.platform.sync.pipeline import ProcessingRequirement

    processing_requirement = ProcessingRequirement.CHUNKS_AND_EMBEDDINGS

    def __init__(self, soft_fail: bool = False):
        """Initialize the Vespa destination.

        Args:
            soft_fail: If True, errors won't fail the sync (default False - Vespa is primary)
        """
        super().__init__(soft_fail=soft_fail)
        self.collection_id: Optional[UUID] = None
        self.organization_id: Optional[UUID] = None

        # Components (initialized in create())
        self._client: Optional[VespaClient] = None
        self._transformer: Optional[EntityTransformer] = None
        self._query_builder: Optional[QueryBuilder] = None

    @classmethod
    async def create(
        cls,
        credentials: Optional[Any] = None,
        config: Optional[dict] = None,
        collection_id: Optional[UUID] = None,
        organization_id: Optional[UUID] = None,
        vector_size: Optional[int] = None,
        logger: Optional[ContextualLogger] = None,
        soft_fail: bool = False,
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
            soft_fail: If True, errors won't fail the sync (default False - Vespa is primary)
            **kwargs: Additional keyword arguments (unused)

        Returns:
            Configured VespaDestination instance
        """
        instance = cls(soft_fail=soft_fail)
        instance.set_logger(logger or default_logger)
        instance.collection_id = collection_id
        instance.organization_id = organization_id

        # Initialize components
        instance._client = await VespaClient.connect(logger=instance.logger)
        instance._transformer = EntityTransformer(
            collection_id=collection_id,
            logger=instance.logger,
        )
        instance._query_builder = QueryBuilder()

        instance.logger.info(
            f"Connected to Vespa at {settings.vespa_url} for collection {collection_id} "
            f"(soft_fail={'enabled' if soft_fail else 'disabled'})"
        )

        return instance

    # -------------------------------------------------------------------------
    # Public API - WHAT (not HOW)
    # -------------------------------------------------------------------------

    async def setup_collection(self, vector_size: Optional[int] = None) -> None:
        """Set up collection in Vespa.

        Note: Vespa schema is deployed separately via vespa-deploy.
        This method is a no-op but kept for interface compatibility.
        """
        self.logger.debug("Vespa schema is managed via vespa-deploy, skipping setup_collection")

    async def bulk_insert(self, entities: List[BaseEntity]) -> None:
        """Transform entities and batch feed to Vespa.

        Args:
            entities: List of entities to insert
        """
        if not entities:
            return

        if not self._client:
            raise RuntimeError("Vespa client not initialized. Call create() first.")

        total_start = time.perf_counter()
        self.logger.info(f"[VespaDestination] Starting bulk_insert for {len(entities)} entities")

        # Transform entities
        transform_start = time.perf_counter()
        docs_by_schema = self._transformer.transform_batch(entities)

        # Convert to dict format for client
        docs_dict = dict(docs_by_schema.items())
        total_docs = sum(len(docs) for docs in docs_dict.values())
        transform_ms = (time.perf_counter() - transform_start) * 1000

        self.logger.info(
            f"[VespaDestination] Transform: {transform_ms:.1f}ms "
            f"for {len(entities)} chunks → {total_docs} docs"
        )

        if total_docs == 0:
            self.logger.warning("No documents to feed after transformation")
            return

        # Feed documents
        feed_start = time.perf_counter()
        result = await self._client.feed_documents(docs_by_schema)
        feed_ms = (time.perf_counter() - feed_start) * 1000

        total_ms = (time.perf_counter() - total_start) * 1000
        self.logger.info(
            f"[VespaDestination] TOTAL bulk_insert: {total_ms:.1f}ms | "
            f"transform={transform_ms:.0f}ms, feed={feed_ms:.0f}ms | "
            f"{result.success_count} success, {len(result.failed_docs)} failed"
        )

        if result.failed_docs:
            self._handle_feed_failures(result.failed_docs, total_docs)

    def _handle_feed_failures(self, failed_docs: List[tuple], total_docs: int) -> None:
        """Log and raise error for feed failures."""
        self.logger.error(f"{len(failed_docs)}/{total_docs} documents failed to feed")
        for doc_id, status, body in failed_docs[:5]:
            self.logger.error(f"  Failed {doc_id}: status={status}, body={body}")

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

    async def delete_by_sync_id(self, sync_id: UUID) -> None:
        """Delete all documents from a sync run.

        Args:
            sync_id: The sync ID to delete documents for
        """
        if not self._client:
            raise RuntimeError("Vespa client not initialized")

        await self._client.delete_by_sync_id(sync_id, self.collection_id)

    async def delete_by_collection_id(self, collection_id: UUID) -> None:
        """Delete all documents for a collection.

        Args:
            collection_id: The collection ID to delete documents for
        """
        if not self._client:
            raise RuntimeError("Vespa client not initialized")

        await self._client.delete_by_collection_id(collection_id)

    async def bulk_delete_by_parent_ids(self, parent_ids: List[str], sync_id: UUID) -> None:
        """Delete all documents for multiple parent IDs.

        Args:
            parent_ids: List of parent entity IDs
            sync_id: The sync ID for scoping (unused, kept for interface)
        """
        if not parent_ids or not self._client:
            return

        await self._client.delete_by_parent_ids(parent_ids, self.collection_id)

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
    ) -> List[AirweaveSearchResult]:
        """Execute hybrid search against Vespa.

        Args:
            queries: List of search query texts (primary + expanded)
            airweave_collection_id: Airweave collection UUID for filtering
            limit: Maximum number of results
            offset: Results to skip (pagination)
            filter: Optional filter dict
            dense_embeddings: Pre-computed dense embeddings for neural/hybrid search
            sparse_embeddings: Pre-computed sparse embeddings for keyword scoring
            retrieval_strategy: Search strategy - "hybrid", "neural", or "keyword"
            temporal_config: Ignored (not yet supported)

        Returns:
            List of AirweaveSearchResult objects (unified format)
        """
        if not self._client:
            raise RuntimeError("Vespa client not initialized. Call create() first.")

        primary_query = queries[0] if queries else ""

        if len(queries) > 1:
            self.logger.info(f"[VespaSearch] Using query expansion with {len(queries)} queries")

        self.logger.debug(
            f"[VespaSearch] Executing search: query='{primary_query[:50]}...', "
            f"num_queries={len(queries)}, limit={limit}, strategy={retrieval_strategy}"
        )

        # Validate embeddings based on retrieval strategy
        if retrieval_strategy == "neural" or retrieval_strategy == "hybrid":
            if not dense_embeddings:
                raise ValueError(
                    "Vespa requires pre-computed dense embeddings for neural/hybrid search. "
                    "Ensure EmbedQuery operation ran before Retrieval."
                )
            if len(dense_embeddings) != len(queries):
                raise ValueError(
                    f"Dense embedding count ({len(dense_embeddings)}) does not match "
                    f"query count ({len(queries)}). Each query needs an embedding."
                )

        if retrieval_strategy == "keyword" or retrieval_strategy == "hybrid":
            if not sparse_embeddings:
                raise ValueError(
                    "Vespa requires pre-computed sparse embeddings for keyword/hybrid search. "
                    "Ensure EmbedQuery operation ran before Retrieval."
                )

        # Build YQL and params
        yql = self._query_builder.build_yql(
            queries, airweave_collection_id, filter, retrieval_strategy
        )
        query_params = self._query_builder.build_params(
            queries, limit, offset, dense_embeddings, sparse_embeddings, retrieval_strategy
        )
        query_params["yql"] = yql

        self.logger.debug(f"[VespaSearch] YQL: {yql}")

        # Execute query
        response = await self._client.execute_query(query_params)

        # Convert results (pagination handled server-side via query params)
        results = self._client.convert_hits_to_results(response.hits)

        self.logger.debug(f"[VespaSearch] Retrieved {len(results)} results")

        return results

    # -------------------------------------------------------------------------
    # Filter translation (exposed for external use)
    # -------------------------------------------------------------------------

    def translate_filter(self, filter: Optional[Dict[str, Any]]) -> Optional[str]:
        """Translate Airweave filter to Vespa YQL filter string.

        Exposed for external callers that need direct filter translation.

        Args:
            filter: Airweave canonical filter dict

        Returns:
            YQL filter string or None
        """
        return self._query_builder.filter_translator.translate(filter)

    def translate_temporal(
        self, config: Optional[AirweaveTemporalConfig]
    ) -> Optional[Dict[str, Any]]:
        """Translate temporal config (not yet implemented).

        Args:
            config: Temporal relevance configuration

        Returns:
            None - temporal relevance not yet supported
        """
        return None

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    async def get_vector_config_names(self) -> List[str]:
        """Get vector config names.

        Returns:
            List of vector field names configured in Vespa schema
        """
        return ["dense_embedding"]

    async def close_connection(self) -> None:
        """Close the Vespa connection."""
        if self._client:
            await self._client.close()
            self._client = None
