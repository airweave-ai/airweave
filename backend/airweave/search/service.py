"""Enhanced search service with configurable operations.

This service uses a modular architecture where search functionality
is broken down into composable operations that can be configured
and executed in a flexible pipeline.
"""

import time
from typing import Any, Dict, List, Literal
from uuid import UUID

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.schemas.search import SearchRequest, SearchResponse
from airweave.search.factory import factory
from airweave.search.helpers import search_helpers
from airweave.search.orchestrator import orchestrator

# Type alias for destination
SearchDestination = Literal["qdrant", "vespa"]


class SearchService:
    """Search service."""

    async def search(
        self,
        request_id: str,
        readable_collection_id: str,
        search_request: SearchRequest,
        stream: bool,
        db: AsyncSession,
        ctx: ApiContext,
        *,
        dense_embedder: DenseEmbedderProtocol,
        sparse_embedder: SparseEmbedderProtocol,
        destination_override: SearchDestination | None = None,
    ) -> SearchResponse:
        """Search a collection.

        Args:
            request_id: Unique request identifier
            readable_collection_id: Collection readable ID to search
            search_request: Search parameters
            stream: Whether to enable SSE streaming
            db: Database session
            ctx: API context
            dense_embedder: Domain dense embedder for generating neural embeddings
            sparse_embedder: Domain sparse embedder for generating BM25 embeddings
            destination_override: If provided, override the default destination
                ('qdrant' or 'vespa'). If None, uses SyncConfig default.

        Returns:
            SearchResponse with results
        """
        start_time = time.monotonic()

        collection = await crud.collection.get_by_readable_id(
            db, readable_id=readable_collection_id, ctx=ctx
        )
        if not collection:
            raise NotFoundException(message=f"Collection '{readable_collection_id}' not found")

        ctx.logger.debug("Building search context")
        search_context = await factory.build(
            request_id,
            collection.id,
            readable_collection_id,
            search_request,
            stream,
            ctx,
            db,
            dense_embedder=dense_embedder,
            sparse_embedder=sparse_embedder,
            destination_override=destination_override,
        )

        ctx.logger.debug("Executing search")
        response, state = await orchestrator.run(ctx, search_context)

        # Handle any federated source auth failures (mark connections as unauthenticated)
        await self._handle_failed_federated_auth(db, state, ctx)

        duration_ms = (time.monotonic() - start_time) * 1000
        ctx.logger.debug(f"Search completed in {duration_ms:.2f}ms")

        # Track search completion to PostHog
        from airweave.analytics.search_analytics import track_search_completion

        # Extract search configuration for analytics
        search_config = {
            "retrieval_strategy": (
                search_context.retrieval.strategy.value if search_context.retrieval else "none"
            ),
            "temporal_relevance": 0.0,
            "expand_query": search_context.query_expansion is not None,
            "interpret_filters": search_context.query_interpretation is not None,
            "rerank": search_context.reranking is not None,
            "generate_answer": search_context.generate_answer is not None,
            "limit": search_context.retrieval.limit if search_context.retrieval else 0,
            "offset": search_context.retrieval.offset if search_context.retrieval else 0,
        }

        # Track the search event with state for automatic metrics extraction
        # TODO: use background task to track search completion, not blocking the response
        track_search_completion(
            ctx=ctx,
            query=search_context.query,
            collection_slug=readable_collection_id,
            duration_ms=duration_ms,
            results=response.results,
            completion=response.completion,
            search_type="streaming" if stream else "regular",
            status="success",
            state=state,  # Pass state for automatic metrics extraction
            **search_config,
        )

        # Persist search data to database
        # TODO: use background task to persist search data, not blocking the response
        await search_helpers.persist_search_data(
            db=db,
            search_context=search_context,
            search_response=response,
            ctx=ctx,
            duration_ms=duration_ms,
        )

        return response

    async def search_admin(
        self,
        request_id: str,
        readable_collection_id: str,
        search_request: SearchRequest,
        db: AsyncSession,
        ctx: ApiContext,
        *,
        dense_embedder: DenseEmbedderProtocol,
        sparse_embedder: SparseEmbedderProtocol,
        destination: SearchDestination = "qdrant",
    ) -> SearchResponse:
        """Admin search with destination selection (no ACL filtering by logged-in user).

        Allows searching any collection regardless of organization with selectable
        destination (Qdrant or Vespa). This is primarily for migration testing
        and admin support operations.

        Args:
            request_id: Unique request identifier
            readable_collection_id: Collection readable ID to search
            search_request: Search parameters
            db: Database session
            ctx: API context
            dense_embedder: Domain dense embedder for generating neural embeddings
            sparse_embedder: Domain sparse embedder for generating BM25 embeddings
            destination: Search destination ('qdrant' or 'vespa')

        Returns:
            SearchResponse with results
        """
        start_time = time.monotonic()

        # Get collection without organization filtering
        from airweave.models.collection import Collection

        result = await db.execute(
            sa_select(Collection).where(Collection.readable_id == readable_collection_id)
        )
        collection = result.scalar_one_or_none()

        if not collection:
            raise NotFoundException(message=f"Collection '{readable_collection_id}' not found")

        ctx.logger.info(
            f"Admin searching collection {readable_collection_id} "
            f"(org: {collection.organization_id}) using destination: {destination}"
        )

        ctx.logger.debug("Building admin search context")
        search_context = await factory.build(
            request_id=request_id,
            collection_id=collection.id,
            readable_collection_id=readable_collection_id,
            search_request=search_request,
            stream=False,
            ctx=ctx,
            db=db,
            dense_embedder=dense_embedder,
            sparse_embedder=sparse_embedder,
            destination_override=destination,
            skip_organization_check=True,
        )

        ctx.logger.debug("Executing admin search")
        response, state = await orchestrator.run(ctx, search_context)

        duration_ms = (time.monotonic() - start_time) * 1000
        ctx.logger.info(
            f"Admin search completed ({destination}): "
            f"{len(response.results)} results in {duration_ms:.2f}ms"
        )

        return response

    async def search_as_user(
        self,
        request_id: str,
        readable_collection_id: str,
        search_request: SearchRequest,
        db: AsyncSession,
        ctx: ApiContext,
        user_principal: str,
        *,
        dense_embedder: DenseEmbedderProtocol,
        sparse_embedder: SparseEmbedderProtocol,
        destination: SearchDestination = "vespa",
    ) -> SearchResponse:
        """Search as a specific user with ACL filtering.

        Resolves the specified user's group memberships from the
        access_control_membership table and filters results accordingly.
        This is primarily for testing ACL sync correctness and verifying
        user permissions.

        Args:
            request_id: Unique request identifier
            readable_collection_id: Collection readable ID to search
            search_request: Search parameters
            db: Database session
            ctx: API context
            user_principal: Username to search as (e.g., "john" or "john@example.com")
            dense_embedder: Domain dense embedder for generating neural embeddings
            sparse_embedder: Domain sparse embedder for generating BM25 embeddings
            destination: Search destination ('qdrant' or 'vespa')

        Returns:
            SearchResponse with results filtered by user's access permissions
        """
        start_time = time.monotonic()

        # Get collection without organization filtering
        from airweave.models.collection import Collection
        from airweave.platform.access_control.broker import access_broker

        result = await db.execute(
            sa_select(Collection).where(Collection.readable_id == readable_collection_id)
        )
        collection = result.scalar_one_or_none()

        if not collection:
            raise NotFoundException(message=f"Collection '{readable_collection_id}' not found")

        ctx.logger.info(
            f"Searching collection {readable_collection_id} as user '{user_principal}' "
            f"(org: {collection.organization_id}) using destination: {destination}"
        )

        # Resolve access context for the specified user
        access_context = await access_broker.resolve_access_context_for_collection(
            db=db,
            user_principal=user_principal,
            readable_collection_id=readable_collection_id,
            organization_id=collection.organization_id,
        )

        if access_context is None:
            ctx.logger.info(
                f"[SearchAsUser] Collection {readable_collection_id} has no "
                "access-control-enabled sources. Returning unfiltered results."
            )
            # Search without ACL override if collection has no AC sources
            user_principal_for_factory = None
        else:
            ctx.logger.info(
                f"[SearchAsUser] Resolved {len(access_context.all_principals)} principals "
                f"for user '{user_principal}': {access_context.all_principals}"
            )
            user_principal_for_factory = user_principal

        ctx.logger.debug("Building search context with user ACL override")
        search_context = await factory.build(
            request_id=request_id,
            collection_id=collection.id,
            readable_collection_id=readable_collection_id,
            search_request=search_request,
            stream=False,
            ctx=ctx,
            db=db,
            dense_embedder=dense_embedder,
            sparse_embedder=sparse_embedder,
            destination_override=destination,
            user_principal_override=user_principal_for_factory,
            skip_organization_check=True,
        )

        ctx.logger.debug("Executing search with user ACL")
        response, state = await orchestrator.run(ctx, search_context)

        duration_ms = (time.monotonic() - start_time) * 1000
        ctx.logger.info(
            f"Search as '{user_principal}' completed ({destination}): "
            f"{len(response.results)} results in {duration_ms:.2f}ms"
        )

        return response

    async def _handle_failed_federated_auth(
        self,
        db: AsyncSession,
        state: Dict[str, Any],
        ctx: ApiContext,
    ) -> None:
        """Mark source connections as unauthenticated on federated auth errors."""
        failed_conn_ids: List[str] = state.get("failed_federated_auth", [])
        if not failed_conn_ids:
            return

        for conn_id in failed_conn_ids:
            source_conn = await crud.source_connection.get(db, id=UUID(conn_id), ctx=ctx)
            if source_conn:
                await crud.source_connection.update(
                    db, db_obj=source_conn, obj_in={"is_authenticated": False}, ctx=ctx
                )
                ctx.logger.warning(f"Marked source connection {conn_id} as unauthenticated")


# TODO: clean search results


service = SearchService()
