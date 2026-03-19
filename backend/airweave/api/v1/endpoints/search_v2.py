"""Search V2 endpoints — instant, classic, agentic tiers.

New routes alongside old search endpoints. Old endpoints remain untouched.

Design: endpoints emit SearchStartedEvent (they own the request).
Services emit SearchCompletedEvent/SearchFailedEvent (they own the execution).
"""

import asyncio
import json

from fastapi import Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import StreamingResponse

from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.deps import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.core.events.search import SearchStartedEvent, SearchTier
from airweave.core.protocols import EventBus, PubSub
from airweave.core.shared_models import FeatureFlag
from airweave.domains.search.protocols import (
    AgenticSearchServiceProtocol,
    ClassicSearchServiceProtocol,
    InstantSearchServiceProtocol,
)
from airweave.domains.usage.protocols import UsageLimitCheckerProtocol
from airweave.domains.usage.types import ActionType
from airweave.schemas.search_v2 import (
    AgenticSearchRequest,
    ClassicSearchRequest,
    InstantSearchRequest,
    InternalAgenticSearchRequest,
    SearchV2Response,
)

router = TrailingSlashRouter()


@router.post("/{readable_id}/search/instant", response_model=SearchV2Response)
async def instant_search(
    readable_id: str = Path(...),
    request: InstantSearchRequest = ...,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    usage_checker: UsageLimitCheckerProtocol = Inject(UsageLimitCheckerProtocol),
    event_bus: EventBus = Inject(EventBus),
    service: InstantSearchServiceProtocol = Inject(InstantSearchServiceProtocol),
) -> SearchV2Response:
    """Instant search — embed query, fire at Vespa, return results."""
    await usage_checker.is_allowed(db, ctx.organization.id, ActionType.QUERIES)

    await event_bus.publish(
        SearchStartedEvent(
            organization_id=ctx.organization.id,
            request_id=ctx.request_id,
            tier=SearchTier.INSTANT,
            collection_readable_id=readable_id,
            query=request.query,
            plan=ctx.billing_plan,
            retrieval_strategy=request.retrieval_strategy.value,
            filter=[f.model_dump() for f in request.filter] if request.filter else None,
            limit=request.limit,
            offset=request.offset,
        )
    )

    results = await service.search(db, ctx, readable_id, request)
    return SearchV2Response(results=results.results)


@router.post("/{readable_id}/search/classic", response_model=SearchV2Response)
async def classic_search(
    readable_id: str = Path(...),
    request: ClassicSearchRequest = ...,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    usage_checker: UsageLimitCheckerProtocol = Inject(UsageLimitCheckerProtocol),
    event_bus: EventBus = Inject(EventBus),
    service: ClassicSearchServiceProtocol = Inject(ClassicSearchServiceProtocol),
) -> SearchV2Response:
    """Classic search — LLM generates search plan, execute against Vespa."""
    await usage_checker.is_allowed(db, ctx.organization.id, ActionType.QUERIES)

    await event_bus.publish(
        SearchStartedEvent(
            organization_id=ctx.organization.id,
            request_id=ctx.request_id,
            tier=SearchTier.CLASSIC,
            collection_readable_id=readable_id,
            query=request.query,
            plan=ctx.billing_plan,
            filter=[f.model_dump() for f in request.filter] if request.filter else None,
            limit=request.limit,
            offset=request.offset,
        )
    )

    results = await service.search(db, ctx, readable_id, request)
    return SearchV2Response(results=results.results)


@router.post("/{readable_id}/search/agentic", response_model=SearchV2Response)
async def agentic_search(
    readable_id: str = Path(...),
    request: AgenticSearchRequest = ...,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    usage_checker: UsageLimitCheckerProtocol = Inject(UsageLimitCheckerProtocol),
    event_bus: EventBus = Inject(EventBus),
    service: AgenticSearchServiceProtocol = Inject(AgenticSearchServiceProtocol),
) -> SearchV2Response:
    """Agentic search — full agent loop with tool calling."""
    if not ctx.has_feature(FeatureFlag.AGENTIC_SEARCH):
        raise HTTPException(
            status_code=403,
            detail="AGENTIC_SEARCH feature not enabled for this organization",
        )
    await usage_checker.is_allowed(db, ctx.organization.id, ActionType.TOKENS)

    await event_bus.publish(
        SearchStartedEvent(
            organization_id=ctx.organization.id,
            request_id=ctx.request_id,
            tier=SearchTier.AGENTIC,
            collection_readable_id=readable_id,
            query=request.query,
            plan=ctx.billing_plan,
            thinking=request.thinking,
            filter=[f.model_dump() for f in request.filter] if request.filter else None,
            limit=request.limit,
        )
    )

    # Service emits SearchCompletedEvent internally
    results = await service.search(db, ctx, readable_id, request)
    return SearchV2Response(results=results.results)


# ── Streaming agentic search ──────────────────────────────────────────


async def _run_agentic_search_v2(
    service: AgenticSearchServiceProtocol,
    ctx: ApiContext,
    readable_id: str,
    request: AgenticSearchRequest,
    pubsub: PubSub,
) -> None:
    """Run agentic search in background. All exceptions caught to guarantee error event."""
    try:
        from airweave.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as search_db:
            await service.search(search_db, ctx, readable_id, request)
    except Exception as e:
        ctx.logger.exception(f"[AgenticSearchV2] Error in stream {ctx.request_id}: {e}")
        # Safety net: if the service crashed before publishing a failed event,
        # publish error directly to PubSub so the SSE stream can terminate.
        try:
            await pubsub.publish(
                "agentic_search_v2",
                ctx.request_id,
                json.dumps({"type": "error", "message": str(e)}),
            )
        except Exception:
            ctx.logger.error(f"[AgenticSearchV2] Failed to emit error for {ctx.request_id}")


async def _cleanup_stream(search_task: asyncio.Task, ps: object) -> None:
    """Cancel the search task if still running and close the PubSub subscription."""
    if not search_task.done():
        search_task.cancel()
        try:
            await search_task
        except Exception:
            pass
    try:
        await ps.close()
    except Exception:
        pass


def _parse_sse_event(data: str) -> str:
    """Extract the event type from a JSON SSE payload, returning empty string on failure."""
    try:
        parsed = json.loads(data)
        return parsed.get("type", "")
    except json.JSONDecodeError:
        return ""


async def _agentic_event_stream_v2(
    ps: object,
    search_task: asyncio.Task,
    ctx: ApiContext,
):
    """Generate SSE events from PubSub messages for agentic search V2."""
    try:
        async for message in ps.listen():
            if message["type"] != "message":
                continue
            data = message["data"]
            yield f"data: {data}\n\n"
            event_type = _parse_sse_event(data)

            if event_type == "done":
                break

            if event_type == "error":
                break
    except asyncio.CancelledError:
        pass
    except Exception as e:
        error_data = json.dumps({"type": "error", "message": str(e)})
        yield f"data: {error_data}\n\n"
    finally:
        await _cleanup_stream(search_task, ps)


@router.post("/{readable_id}/search/agentic/stream")
async def stream_agentic_search(
    readable_id: str = Path(...),
    request: AgenticSearchRequest = ...,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    usage_checker: UsageLimitCheckerProtocol = Inject(UsageLimitCheckerProtocol),
    event_bus: EventBus = Inject(EventBus),
    pubsub: PubSub = Inject(PubSub),
    service: AgenticSearchServiceProtocol = Inject(AgenticSearchServiceProtocol),
) -> StreamingResponse:
    """Streaming agentic search via Server-Sent Events."""
    if not ctx.has_feature(FeatureFlag.AGENTIC_SEARCH):
        raise HTTPException(
            status_code=403,
            detail="AGENTIC_SEARCH feature not enabled for this organization",
        )

    await usage_checker.is_allowed(db, ctx.organization.id, ActionType.TOKENS)

    # Subscribe first so we don't miss the started event
    ps = await pubsub.subscribe("agentic_search_v2", ctx.request_id)

    # Emit started event — flows through relay to PubSub as SSE "started"
    await event_bus.publish(
        SearchStartedEvent(
            organization_id=ctx.organization.id,
            request_id=ctx.request_id,
            tier=SearchTier.AGENTIC,
            collection_readable_id=readable_id,
            query=request.query,
            plan=ctx.billing_plan,
            thinking=request.thinking,
            filter=[f.model_dump() for f in request.filter] if request.filter else None,
            limit=request.limit,
        )
    )

    search_task = asyncio.create_task(
        _run_agentic_search_v2(service, ctx, readable_id, request, pubsub)
    )

    return StreamingResponse(
        _agentic_event_stream_v2(ps, search_task, ctx),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Admin endpoints (model override for evals) ──────────────────────

admin_router = TrailingSlashRouter()


@admin_router.post("/{readable_id}/search/agentic/stream")
async def admin_stream_agentic_search(
    readable_id: str = Path(...),
    request: InternalAgenticSearchRequest = ...,
    db: AsyncSession = Depends(deps.get_db),
    ctx: ApiContext = Depends(deps.get_context),
    usage_checker: UsageLimitCheckerProtocol = Inject(UsageLimitCheckerProtocol),
    event_bus: EventBus = Inject(EventBus),
    pubsub: PubSub = Inject(PubSub),
    service: AgenticSearchServiceProtocol = Inject(AgenticSearchServiceProtocol),
) -> StreamingResponse:
    """Admin streaming agentic search with optional model override (for evals)."""
    if not ctx.has_feature(FeatureFlag.AGENTIC_SEARCH):
        raise HTTPException(
            status_code=403,
            detail="AGENTIC_SEARCH feature not enabled for this organization",
        )

    await usage_checker.is_allowed(db, ctx.organization.id, ActionType.TOKENS)

    # Build the effective service — with model override if specified
    effective_service = service
    if request.model:
        from airweave.adapters.llm.override import create_llm_from_override

        override_llm = create_llm_from_override(request.model)
        effective_service = service.with_llm(override_llm)  # type: ignore[union-attr]

    ps = await pubsub.subscribe("agentic_search_v2", ctx.request_id)

    await event_bus.publish(
        SearchStartedEvent(
            organization_id=ctx.organization.id,
            request_id=ctx.request_id,
            tier=SearchTier.AGENTIC,
            collection_readable_id=readable_id,
            query=request.query,
            plan=ctx.billing_plan,
            thinking=request.thinking,
            filter=[f.model_dump() for f in request.filter] if request.filter else None,
            limit=request.limit,
        )
    )

    search_task = asyncio.create_task(
        _run_agentic_search_v2(effective_service, ctx, readable_id, request, pubsub)
    )

    return StreamingResponse(
        _agentic_event_stream_v2(ps, search_task, ctx),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
