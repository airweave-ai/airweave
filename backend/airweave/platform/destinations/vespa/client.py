"""Vespa client - low-level I/O operations for Vespa.

This module encapsulates all direct communication with Vespa, including:
- Connection management
- Document feeding (bulk insert)
- Document deletion
- Query execution
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional
from urllib.parse import quote
from uuid import UUID

import httpx

from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.platform.destinations.vespa.config import (
    ALL_VESPA_SCHEMAS,
    DELETE_BATCH_SIZE,
    FEED_MAX_CONNECTIONS,
    FEED_MAX_QUEUE_SIZE,
    FEED_MAX_WORKERS,
)
from airweave.platform.destinations.vespa.types import (
    DeleteResult,
    FeedResult,
    VespaDocument,
    VespaQueryResponse,
)
from airweave.schemas.search_result import (
    AccessControlResult,
    AirweaveSearchResult,
    BreadcrumbResult,
    SystemMetadataResult,
)

if TYPE_CHECKING:
    from vespa.application import Vespa


class VespaClient:
    """Low-level Vespa client wrapper.

    Handles all I/O operations with Vespa, including:
    - Connection management
    - Document feeding via feed_iterable
    - Document deletion via selection-based API
    - Query execution
    """

    def __init__(
        self,
        app: "Vespa",
        logger: Optional[ContextualLogger] = None,
    ):
        """Initialize the Vespa client.

        Args:
            app: Connected pyvespa Vespa application instance
            logger: Optional logger for debug/warning messages
        """
        self.app = app
        self._logger = logger or default_logger

    @classmethod
    async def connect(
        cls,
        url: Optional[str] = None,
        port: Optional[int] = None,
        logger: Optional[ContextualLogger] = None,
    ) -> "VespaClient":
        """Create and connect a Vespa client.

        Args:
            url: Vespa URL (defaults to settings.VESPA_URL)
            port: Vespa port (defaults to settings.VESPA_PORT)
            logger: Optional logger

        Returns:
            Connected VespaClient instance
        """
        from vespa.application import Vespa

        vespa_url = url or settings.VESPA_URL
        vespa_port = port or settings.VESPA_PORT

        app = Vespa(url=vespa_url, port=vespa_port)

        log = logger or default_logger
        log.info(f"Connected to Vespa at {vespa_url}:{vespa_port}")

        return cls(app=app, logger=logger)

    async def close(self) -> None:
        """Close the Vespa connection."""
        self._logger.debug("Closing Vespa connection")
        self.app = None

    # -------------------------------------------------------------------------
    # Feed Operations
    # -------------------------------------------------------------------------

    async def feed_documents(
        self,
        docs_by_schema: Dict[str, List[VespaDocument]],
        callback: Optional[Callable] = None,
    ) -> FeedResult:
        """Feed documents to Vespa using feed_iterable.

        Uses pyvespa's feed_iterable for efficient concurrent feeding via HTTP/2
        multiplexing. Documents are grouped by schema and fed separately.

        IMPORTANT: feed_iterable is synchronous, so we run it in a thread pool.

        Args:
            docs_by_schema: Dict mapping schema name to list of VespaDocuments
            callback: Optional callback for tracking progress

        Returns:
            FeedResult with success count and failed documents
        """
        result = FeedResult()

        def track_callback(response, doc_id: str):
            if response.is_successful():
                result.success_count += 1
            else:
                result.failed_docs.append((doc_id, response.status_code, response.json))

        actual_callback = callback or track_callback

        # Feed each schema's documents
        for schema, docs in docs_by_schema.items():
            if not docs:
                continue

            # Convert VespaDocument to dict format expected by feed_iterable
            doc_dicts = [{"id": doc.id, "fields": doc.fields} for doc in docs]

            def _feed_sync(docs_iter=doc_dicts, schema_name=schema):
                self.app.feed_iterable(
                    iter=docs_iter,
                    schema=schema_name,
                    namespace="airweave",
                    callback=actual_callback,
                    max_queue_size=FEED_MAX_QUEUE_SIZE,
                    max_workers=FEED_MAX_WORKERS,
                    max_connections=FEED_MAX_CONNECTIONS,
                )

            schema_start = time.perf_counter()
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(_feed_sync),
                    timeout=settings.VESPA_TIMEOUT,
                )
            except asyncio.TimeoutError:
                schema_ms = (time.perf_counter() - schema_start) * 1000
                self._logger.error(
                    f"[VespaClient] Feed to schema '{schema}' TIMED OUT after "
                    f"{schema_ms:.0f}ms ({len(docs)} docs)"
                )
                raise
            schema_ms = (time.perf_counter() - schema_start) * 1000

            self._logger.info(
                f"[VespaClient] Fed schema '{schema}': {len(docs)} docs in {schema_ms:.1f}ms "
                f"({schema_ms / len(docs):.1f}ms/doc)"
            )

        return result

    # -------------------------------------------------------------------------
    # Delete Operations
    # -------------------------------------------------------------------------

    async def delete_by_selection(self, schema: str, selection: str) -> DeleteResult:
        """Delete documents using Vespa's selection-based bulk delete API.

        This is faster than query-then-delete because it performs server-side
        deletion in a single streaming operation.

        Uses: DELETE /document/v1/{namespace}/{doctype}/docid?selection={expr}&cluster={cluster}

        Args:
            schema: The Vespa schema/document type to delete from
            selection: Document selection expression (e.g., "field=='value'")

        Returns:
            DeleteResult with count of deleted documents
        """
        url = self._build_bulk_delete_url(schema, selection)
        self._logger.debug(f"[VespaClient] Bulk delete from {schema} with selection: {selection}")

        deleted_count = 0
        try:
            async with httpx.AsyncClient(timeout=settings.VESPA_TIMEOUT) as client:
                async with client.stream("DELETE", url) as response:
                    if response.status_code == 200:
                        deleted_count = await self._parse_bulk_delete_response(response)
                    else:
                        await self._log_delete_error(response)
        except httpx.TimeoutException:
            self._logger.error(
                f"[VespaClient] Bulk delete timed out after {settings.VESPA_TIMEOUT}s"
            )
        except Exception as e:
            self._logger.error(f"[VespaClient] Bulk delete error: {e}")

        if deleted_count > 0:
            self._logger.info(f"[VespaClient] Deleted {deleted_count} documents from {schema}")
        else:
            self._logger.debug(f"[VespaClient] No documents to delete from {schema}")

        return DeleteResult(deleted_count=deleted_count, schema=schema)

    async def delete_by_sync_id(self, sync_id: UUID, collection_id: UUID) -> List[DeleteResult]:
        """Delete all documents for a sync ID across all schemas.

        Args:
            sync_id: The sync ID to delete documents for
            collection_id: The collection ID to scope deletion

        Returns:
            List of DeleteResult for each schema
        """
        results = []
        for schema in ALL_VESPA_SCHEMAS:
            selection = (
                f"{schema}.airweave_system_metadata_sync_id=='{sync_id}' and "
                f"{schema}.airweave_system_metadata_collection_id=='{collection_id}'"
            )
            result = await self.delete_by_selection(schema, selection)
            results.append(result)
        return results

    async def delete_by_collection_id(self, collection_id: UUID) -> List[DeleteResult]:
        """Delete all documents for a collection across all schemas.

        Args:
            collection_id: The collection ID to delete documents for

        Returns:
            List of DeleteResult for each schema
        """
        results = []
        for schema in ALL_VESPA_SCHEMAS:
            selection = f"{schema}.airweave_system_metadata_collection_id=='{collection_id}'"
            result = await self.delete_by_selection(schema, selection)
            results.append(result)
        return results

    async def delete_by_parent_ids(
        self,
        parent_ids: List[str],
        collection_id: UUID,
        batch_size: int = DELETE_BATCH_SIZE,
    ) -> List[DeleteResult]:
        """Delete all documents for parent IDs across all schemas.

        Batches parent IDs to avoid overly long selection expressions.

        Args:
            parent_ids: List of parent entity IDs
            collection_id: Collection ID to scope deletion
            batch_size: Max parent IDs per batch

        Returns:
            List of DeleteResult for all operations
        """
        if not parent_ids:
            return []

        results = []
        for i in range(0, len(parent_ids), batch_size):
            batch = parent_ids[i : i + batch_size]

            for schema in ALL_VESPA_SCHEMAS:
                parent_conditions = " or ".join(
                    f"{schema}.airweave_system_metadata_original_entity_id=='{pid}'"
                    for pid in batch
                )
                selection = (
                    f"({parent_conditions}) and "
                    f"{schema}.airweave_system_metadata_collection_id=='{collection_id}'"
                )
                result = await self.delete_by_selection(schema, selection)
                results.append(result)

        return results

    def _build_bulk_delete_url(self, schema: str, selection: str) -> str:
        """Build the URL for Vespa bulk delete operation."""
        base_url = f"{settings.VESPA_URL}:{settings.VESPA_PORT}"
        encoded_selection = quote(selection, safe="")
        return (
            f"{base_url}/document/v1/airweave/{schema}/docid"
            f"?selection={encoded_selection}"
            f"&cluster={settings.VESPA_CLUSTER}"
        )

    async def _parse_bulk_delete_response(self, response: httpx.Response) -> int:
        """Parse streaming response from Vespa bulk delete."""
        count = 0
        async for line in response.aiter_lines():
            if not line.strip():
                continue
            try:
                result = json.loads(line)
                if "documentCount" in result:
                    count += result["documentCount"]
                elif "sessionStats" in result:
                    stats = result["sessionStats"]
                    count += stats.get("documentCount", 0)
                elif result.get("id"):
                    count += 1
            except json.JSONDecodeError:
                pass
        return count

    async def _log_delete_error(self, response: httpx.Response) -> None:
        """Log error from failed bulk delete response."""
        body = await response.aread()
        if response.status_code == 400:
            self._logger.error(f"[VespaClient] Invalid selection expression: {body.decode()}")
        else:
            self._logger.error(
                f"[VespaClient] Bulk delete failed ({response.status_code}): {body.decode()}"
            )

    # -------------------------------------------------------------------------
    # Query Operations
    # -------------------------------------------------------------------------

    async def execute_query(self, query_params: Dict[str, Any]) -> VespaQueryResponse:
        """Execute a query against Vespa.

        Runs the query in a thread pool since pyvespa is synchronous.

        Args:
            query_params: Complete Vespa query parameters including YQL

        Returns:
            VespaQueryResponse with hits and metrics
        """
        start_time = time.monotonic()
        try:
            response = await asyncio.to_thread(self.app.query, body=query_params)
        except Exception as e:
            self._logger.error(f"[VespaClient] Vespa query failed: {e}")
            raise RuntimeError(f"Vespa search failed: {e}") from e
        query_time_ms = (time.monotonic() - start_time) * 1000

        # Check for errors
        if not response.is_successful():
            error_msg = getattr(response, "json", {}).get("error", str(response))
            self._logger.error(f"[VespaClient] Vespa returned error: {error_msg}")
            raise RuntimeError(f"Vespa search error: {error_msg}")

        # Extract metrics
        raw_json = response.json if hasattr(response, "json") else {}
        root = raw_json.get("root", {})
        coverage = root.get("coverage", {})
        total_count = root.get("fields", {}).get("totalCount", 0)

        self._logger.info(
            f"[VespaClient] Query completed in {query_time_ms:.1f}ms, "
            f"total={total_count}, hits={len(response.hits or [])}"
        )

        return VespaQueryResponse(
            hits=response.hits or [],
            total_count=total_count,
            coverage_percent=coverage.get("coverage", 100.0),
            query_time_ms=query_time_ms,
        )

    def convert_hits_to_results(self, hits: List[Dict[str, Any]]) -> List[AirweaveSearchResult]:
        """Convert Vespa hits to AirweaveSearchResult objects.

        Transforms Vespa's flat field structure into the unified AirweaveSearchResult
        format.

        Args:
            hits: List of Vespa hit dictionaries

        Returns:
            List of AirweaveSearchResult objects
        """
        results = []
        for i, hit in enumerate(hits):
            fields = hit.get("fields", {})
            self._log_hit_debug(i, fields, hit.get("relevance", 0.0))

            result = AirweaveSearchResult(
                id=hit.get("id", ""),
                score=hit.get("relevance", 0.0),
                entity_id=fields.get("entity_id", ""),
                name=fields.get("name", ""),
                textual_representation=fields.get("textual_representation", ""),
                created_at=self._parse_timestamp(fields.get("created_at")),
                updated_at=self._parse_timestamp(fields.get("updated_at")),
                breadcrumbs=self._extract_breadcrumbs(fields.get("breadcrumbs", [])),
                system_metadata=self._extract_system_metadata(fields),
                access=self._extract_access_control(fields),
                source_fields=self._parse_payload(fields.get("payload")),
            )
            results.append(result)

        return results

    def _log_hit_debug(self, index: int, fields: Dict[str, Any], relevance: float) -> None:
        """Log debug info for first 5 hits."""
        if index < 5:
            entity_name = fields.get("name", "N/A")
            entity_type = fields.get("airweave_system_metadata_entity_type", "N/A")
            self._logger.debug(
                f"[VespaClient] Hit {index}: name='{entity_name[:40] if entity_name else 'N/A'}' "
                f"type={entity_type} relevance={relevance:.4f}"
            )

    def _extract_system_metadata(self, fields: Dict[str, Any]) -> SystemMetadataResult:
        """Extract system metadata from flattened Vespa fields."""
        return SystemMetadataResult(
            entity_type=fields.get("airweave_system_metadata_entity_type", ""),
            source_name=fields.get("airweave_system_metadata_source_name"),
            sync_id=fields.get("airweave_system_metadata_sync_id"),
            sync_job_id=fields.get("airweave_system_metadata_sync_job_id"),
            original_entity_id=fields.get("airweave_system_metadata_original_entity_id"),
            chunk_index=fields.get("airweave_system_metadata_chunk_index"),
        )

    def _extract_access_control(self, fields: Dict[str, Any]) -> Optional[AccessControlResult]:
        """Extract access control from flattened Vespa fields."""
        if "access_is_public" not in fields and "access_viewers" not in fields:
            return None
        return AccessControlResult(
            is_public=fields.get("access_is_public", False),
            viewers=fields.get("access_viewers", []),
        )

    def _extract_breadcrumbs(self, raw_breadcrumbs: List[Any]) -> List[BreadcrumbResult]:
        """Extract breadcrumbs from Vespa list of dicts."""
        breadcrumbs = []
        for bc in raw_breadcrumbs:
            if isinstance(bc, dict):
                breadcrumbs.append(
                    BreadcrumbResult(
                        entity_id=bc.get("entity_id", ""),
                        name=bc.get("name", ""),
                        entity_type=bc.get("entity_type", ""),
                    )
                )
        return breadcrumbs

    def _parse_timestamp(self, epoch_value: Any) -> Optional[datetime]:
        """Convert epoch timestamp to datetime, returning None on failure."""
        if not epoch_value:
            return None
        try:
            return datetime.fromtimestamp(epoch_value)
        except (ValueError, TypeError, OSError):
            return None

    def _parse_payload(self, payload_str: Any) -> Dict[str, Any]:
        """Parse payload JSON string into source_fields dict."""
        if not payload_str or not isinstance(payload_str, str):
            return {}
        try:
            return json.loads(payload_str)
        except json.JSONDecodeError:
            return {}
