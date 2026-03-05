"""Search API endpoints for querying data within collections.

These endpoints are mounted under the `/collections` prefix in `api/v1/api.py`,
enabling powerful semantic and hybrid search across synced data sources.

Key features:
- Hybrid search combining neural (semantic) and keyword (BM25) matching
- Optional query expansion for improved recall
- Filter extraction from natural language queries
- AI-powered answer generation from search results
- Streaming support for real-time results
"""

import asyncio
import json
from typing import Any, Dict, Union

from fastapi import Depends, HTTPException, Path, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.deps import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.core.events.sync import QueryProcessedEvent
from airweave.core.protocols import EventBus, PubSub
from airweave.db.session import AsyncSessionLocal
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.domains.usage.protocols import UsageLimitCheckerProtocol
from airweave.domains.usage.types import ActionType
from airweave.schemas.errors import (
    NotFoundErrorResponse,
    RateLimitErrorResponse,
    ValidationErrorResponse,
)
from airweave.schemas.search import SearchRequest, SearchResponse
from airweave.schemas.search_legacy import LegacySearchRequest, LegacySearchResponse, ResponseType
from airweave.search.legacy_adapter import (
    convert_legacy_request_to_new,
    convert_new_response_to_legacy,
)
from airweave.search.service import service

router = TrailingSlashRouter()


@router.get(
    "/{readable_id}/search",
    response_model=LegacySearchResponse,
    deprecated=True,
    summary="Search Collection (Legacy)",
    description="""**DEPRECATED**: Use POST /collections/{readable_id}/search instead.

This legacy GET endpoint provides basic search functionality via query parameters.
Migrate to the POST endpoint for access to advanced features like:
- Structured filters
- Query expansion
- Reranking
- Streaming responses""",
    responses={
        200: {"model": LegacySearchResponse, "description": "Search results"},
        404: {"model": NotFoundErrorResponse, "description": "Collection Not Found"},
        422: {"model": ValidationErrorResponse, "description": "Validation Error"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def search_get_legacy(
    response: Response,
    readable_id: str = Path(
        ...,
        description="The unique readable identifier of the collection to search",
        json_schema_extra={"example": "customer-support-tickets-x7k9m"},
    ),
    query: str = Query(
        ...,
        description="The search query text to find relevant documents and data",
        json_schema_extra={"example": "How do I reset my password?"},
    ),
    response_type: ResponseType = Query(
        ResponseType.RAW,
        description=(
            "Format of the response: 'raw' returns search results, "
            "'completion' returns AI-generated answers"
        ),
        json_schema_extra={"example": "raw"},
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of results to return",
        json_schema_extra={"example": 10},
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of results to skip for pagination",
        json_schema_extra={"example": 0},
    ),
    recency_bias: float | None = Query(
        None,
        ge=0.0,
        le=1.0,
        description="How much to weigh recency vs similarity (0=similarity only, 1=recency only)",
        json_schema_extra={"example": 0.3},
    ),
    db: AsyncSession = Depends(deps.get_db),
    usage_checker: UsageLimitCheckerProtocol = Inject(UsageLimitCheckerProtocol),
    event_bus: EventBus = Inject(EventBus),
    ctx: ApiContext = Depends(deps.get_context),
    pubsub: PubSub = Inject(PubSub),
    dense_embedder: DenseEmbedderProtocol = Inject(DenseEmbedderProtocol),
    sparse_embedder: SparseEmbedderProtocol = Inject(SparseEmbedderProtocol),
) -> LegacySearchResponse:
    """Legacy GET search endpoint for backwards compatibility."""
    await usage_checker.is_allowed(db, ctx.organization.id, ActionType.QUERIES)

    # Add deprecation warning headers
    response.headers["X-API-Deprecation"] = "true"
    response.headers["X-API-Deprecation-Message"] = (
        "This endpoint is deprecated. Please use POST /collections/{id}/search "
        "with the new SearchRequest schema for improved functionality."
    )

    ctx.logger.info(f"Legacy GET search for collection {readable_id}")

    # Create legacy request from query parameters
    legacy_request = LegacySearchRequest(
        query=query,
        response_type=response_type,
        limit=limit,
        offset=offset,
        recency_bias=recency_bias,
    )

    # Convert to new format
    new_request = convert_legacy_request_to_new(legacy_request)

    new_response = await service.search(
        request_id=ctx.request_id,
        readable_collection_id=readable_id,
        search_request=new_request,
        stream=False,
        db=db,
        ctx=ctx,
        pubsub=pubsub,
        dense_embedder=dense_embedder,
        sparse_embedder=sparse_embedder,
    )

    # Convert back to legacy format
    legacy_response = convert_new_response_to_legacy(new_response, response_type)

    await event_bus.publish(QueryProcessedEvent(organization_id=ctx.organization.id))

    return legacy_response


@router.post(
    "/{readable_id}/search",
    response_model=Union[SearchResponse, LegacySearchResponse],
    summary="Search Collection",
    description="""Search your collection using semantic and hybrid search.

This is the primary search endpoint providing powerful AI-powered search capabilities:

**Search Strategies:**
- **hybrid** (default): Combines neural (semantic) and keyword (BM25) matching
- **neural**: Pure semantic search using embeddings
- **keyword**: Traditional keyword-based BM25 search

**Features:**
- **Query expansion**: Generate query variations to improve recall
- **Filter interpretation**: Extract structured filters from natural language
- **Reranking**: LLM-based reranking for improved relevance
- **Answer generation**: AI-generated answers based on search results

**Note**: Accepts both new SearchRequest and legacy LegacySearchRequest formats
for backwards compatibility.""",
    responses={
        200: {"model": SearchResponse, "description": "Search results with optional AI completion"},
        404: {"model": NotFoundErrorResponse, "description": "Collection Not Found"},
        422: {"model": ValidationErrorResponse, "description": "Validation Error"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def search(
    http_response: Response,
    readable_id: str = Path(
        ...,
        description="The unique readable identifier of the collection to search",
        json_schema_extra={"example": "customer-support-tickets-x7k9m"},
    ),
    search_request: Union[SearchRequest, LegacySearchRequest] = ...,
    db: AsyncSession = Depends(deps.get_db),
    usage_checker: UsageLimitCheckerProtocol = Inject(UsageLimitCheckerProtocol),
    event_bus: EventBus = Inject(EventBus),
    ctx: ApiContext = Depends(deps.get_context),
    pubsub: PubSub = Inject(PubSub),
    dense_embedder: DenseEmbedderProtocol = Inject(DenseEmbedderProtocol),
    sparse_embedder: SparseEmbedderProtocol = Inject(SparseEmbedderProtocol),
) -> Union[SearchResponse, LegacySearchResponse]:
    """Search your collection with AI-powered semantic search."""
    await usage_checker.is_allowed(db, ctx.organization.id, ActionType.QUERIES)

    ctx.logger.info(f"Starting search for collection '{readable_id}'")

    # Determine if this is a legacy request and convert if needed
    is_legacy = isinstance(search_request, LegacySearchRequest)
    requested_response_type = None

    if is_legacy:
        ctx.logger.debug("Processing legacy search request")
        # Add deprecation warning headers
        http_response.headers["X-API-Deprecation"] = "true"
        http_response.headers["X-API-Deprecation-Message"] = (
            "You're using the legacy SearchRequest schema. Please migrate to the new schema."
        )
        requested_response_type = search_request.response_type
        search_request = convert_legacy_request_to_new(search_request)

    # Warn if temporal_relevance was requested but is removed
    if (
        hasattr(search_request, "temporal_relevance")
        and search_request.temporal_relevance is not None
        and search_request.temporal_relevance > 0
    ):
        http_response.headers["X-Feature-Removed"] = "temporal_relevance"
        http_response.headers["X-Feature-Removed-Message"] = (
            "temporal_relevance has been removed and was ignored"
        )

    search_response = await service.search(
        request_id=ctx.request_id,
        readable_collection_id=readable_id,
        search_request=search_request,
        stream=False,
        db=db,
        ctx=ctx,
        pubsub=pubsub,
        dense_embedder=dense_embedder,
        sparse_embedder=sparse_embedder,
        destination_override="vespa",
    )

    ctx.logger.info(f"Search completed for collection '{readable_id}'")
    await event_bus.publish(QueryProcessedEvent(organization_id=ctx.organization.id))

    # Convert response back to legacy format if needed
    if is_legacy:
        return convert_new_response_to_legacy(search_response, requested_response_type)

    return search_response


@router.post("/{readable_id}/search/stream")
async def stream_search_collection_advanced(  # noqa: C901 - streaming orchestration is acceptable
    readable_id: str = Path(
        ..., description="The unique readable identifier of the collection to search"
    ),
    search_request: Union[SearchRequest, LegacySearchRequest] = ...,
    db: AsyncSession = Depends(deps.get_db),
    usage_checker: UsageLimitCheckerProtocol = Inject(UsageLimitCheckerProtocol),
    event_bus: EventBus = Inject(EventBus),
    ctx: ApiContext = Depends(deps.get_context),
    pubsub: PubSub = Inject(PubSub),
    dense_embedder: DenseEmbedderProtocol = Inject(DenseEmbedderProtocol),
    sparse_embedder: SparseEmbedderProtocol = Inject(SparseEmbedderProtocol),
) -> StreamingResponse:
    """Server-Sent Events (SSE) streaming endpoint for advanced search.

    Initializes a streaming session and relays events from Redis Pub/Sub.
    Accepts both new SearchRequest and legacy LegacySearchRequest formats.
    """
    request_id = ctx.request_id
    ctx.logger.info(
        f"[SearchStream] Starting stream for collection '{readable_id}' id={request_id}"
    )

    await usage_checker.is_allowed(db, ctx.organization.id, ActionType.QUERIES)

    if isinstance(search_request, LegacySearchRequest):
        ctx.logger.debug("Processing legacy streaming search request")
        search_request = convert_legacy_request_to_new(search_request)

    ps = await pubsub.subscribe("search", request_id)

    async def _publish_stream_error(
        *, message: str, transient: bool, detail: str | None = None
    ) -> None:
        payload: dict[str, Any] = {
            "type": "error",
            "message": message,
            "transient": transient,
        }
        if detail:
            payload["detail"] = detail
        await pubsub.publish("search", request_id, payload)

    async def _run_search() -> None:
        try:
            async with AsyncSessionLocal() as search_db:
                # Always use Vespa for public endpoints
                await service.search(
                    request_id=request_id,
                    readable_collection_id=readable_id,
                    search_request=search_request,
                    stream=True,
                    db=search_db,
                    ctx=ctx,
                    pubsub=pubsub,
                    dense_embedder=dense_embedder,
                    sparse_embedder=sparse_embedder,
                    destination_override="vespa",
                )
        except ValueError as e:
            await _publish_stream_error(message=str(e), transient=False)
        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, str) else "Search failed"
            await _publish_stream_error(
                message=detail,
                transient=e.status_code >= 500,
            )
        except Exception as e:  # noqa: BLE001 - report to stream
            ctx.logger.exception(
                "[SearchStream] Unexpected failure while executing search %s", request_id
            )
            await _publish_stream_error(
                message="Search stream disconnected. Please retry your search.",
                transient=True,
                detail=str(e),
            )

    search_task = asyncio.create_task(_run_search())

    async def event_stream():  # noqa: C901 - complex loop acceptable
        try:
            import datetime as _dt

            connected_event = {
                "type": "connected",
                "request_id": request_id,
                "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            }
            yield f"data: {json.dumps(connected_event)}\n\n"

            last_heartbeat = asyncio.get_event_loop().time()
            heartbeat_interval = 30

            async for message in ps.listen():
                now = asyncio.get_event_loop().time()
                if now - last_heartbeat > heartbeat_interval:
                    heartbeat_event = {
                        "type": "heartbeat",
                        "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                    }
                    yield f"data: {json.dumps(heartbeat_event)}\n\n"
                    last_heartbeat = now

                if message["type"] == "message":
                    data = message["data"]
                    yield f"data: {data}\n\n"

                    try:
                        parsed = json.loads(data)
                        if isinstance(parsed, dict) and parsed.get("type") == "done":
                            ctx.logger.info(
                                f"[SearchStream] Done event received for search:{request_id}. "
                                "Closing stream"
                            )
                            try:
                                await event_bus.publish(
                                    QueryProcessedEvent(organization_id=ctx.organization.id)
                                )
                            except Exception:
                                pass
                            break
                    except Exception:
                        pass

                elif message["type"] == "subscribe":
                    ctx.logger.info(f"[SearchStream] Subscribed to channel search:{request_id}")
                else:
                    current = asyncio.get_event_loop().time()
                    if current - last_heartbeat > heartbeat_interval:
                        heartbeat_event = {
                            "type": "heartbeat",
                            "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                        }
                        yield f"data: {json.dumps(heartbeat_event)}\n\n"
                        last_heartbeat = current

        except asyncio.CancelledError:
            ctx.logger.info(f"[SearchStream] Cancelled stream id={request_id}")
        except Exception as e:  # noqa: BLE001 - emit error event
            ctx.logger.error(f"[SearchStream] Error id={request_id}: {str(e)}")
            import datetime as _dt

            error_event = {
                "type": "error",
                "transient": True,
                "message": "Search connection interrupted. Please try again.",
                "detail": str(e),
                "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            }
            yield f"data: {json.dumps(error_event)}\n\n"
        finally:
            if not search_task.done():
                search_task.cancel()
                try:
                    await search_task
                except Exception:
                    pass
            try:
                await ps.close()
                ctx.logger.info(
                    f"[SearchStream] Closed pubsub subscription for search:{request_id}"
                )
            except Exception:
                pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/internal/filter-schema")
async def get_filter_schema() -> Dict[str, Any]:
    """Get the JSON schema for filter validation.

    This endpoint returns the JSON schema that can be used to validate
    filter objects in the frontend. Uses the destination-agnostic Airweave
    filter format (must/should/must_not with field conditions).
    """
    return {
        "type": "object",
        "properties": {
            "must": {
                "type": "array",
                "items": {"$ref": "#/$defs/FieldCondition"},
                "description": "All conditions must match (AND)",
            },
            "must_not": {
                "type": "array",
                "items": {"$ref": "#/$defs/FieldCondition"},
                "description": "None of these conditions must match (NOT)",
            },
            "should": {
                "type": "array",
                "items": {"$ref": "#/$defs/FieldCondition"},
                "description": "At least one condition should match (OR)",
            },
            "minimum_should_match": {
                "type": "integer",
                "description": "Minimum number of should conditions that must match",
            },
        },
        "additionalProperties": False,
        "$defs": {
            "FieldCondition": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Field name to filter on",
                    },
                    "match": {
                        "type": "object",
                        "properties": {
                            "value": {
                                "description": "Exact value to match",
                            },
                        },
                    },
                    "range": {
                        "type": "object",
                        "properties": {
                            "gt": {"description": "Greater than"},
                            "gte": {"description": "Greater than or equal"},
                            "lt": {"description": "Less than"},
                            "lte": {"description": "Less than or equal"},
                        },
                    },
                },
                "required": ["key"],
            },
        },
    }
