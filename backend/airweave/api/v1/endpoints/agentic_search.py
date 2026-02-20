"""Agentic search endpoints.

These endpoints provide agentic search capabilities using the agentic_search module.
The agentic_search module creates its own database connection based on its config,
completely separate from the Airweave API's database connection.
"""

import asyncio
import json

from fastapi import Depends, HTTPException, Path
from starlette.responses import StreamingResponse

from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.deps import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.core.guard_rail_service import GuardRailService
from airweave.core.protocols import MetricsService
from airweave.core.pubsub import core_pubsub
from airweave.core.shared_models import ActionType, FeatureFlag
from airweave.search.agentic_search.core.agent import AgenticSearchAgent
from airweave.search.agentic_search.emitter import (
    AgenticSearchLoggingEmitter,
    AgenticSearchPubSubEmitter,
)
from airweave.search.agentic_search.schemas import AgenticSearchRequest, AgenticSearchResponse
from airweave.search.agentic_search.schemas.events import AgenticSearchErrorEvent
from airweave.search.agentic_search.services import AgenticSearchServices

router = TrailingSlashRouter()


@router.post("/{readable_id}/agentic-search", response_model=AgenticSearchResponse)
async def agentic_search(
    request: AgenticSearchRequest,
    readable_id: str = Path(..., description="The unique readable identifier of the collection"),
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
    metrics_service: MetricsService = Inject(MetricsService),
) -> AgenticSearchResponse:
    """Perform agentic search."""
    if not ctx.has_feature(FeatureFlag.AGENTIC_SEARCH):
        raise HTTPException(
            status_code=403,
            detail="AGENTIC_SEARCH feature not enabled for this organization",
        )

    await guard_rail.is_allowed(ActionType.QUERIES)

    services = await AgenticSearchServices.create(ctx, readable_id)

    try:
        emitter = AgenticSearchLoggingEmitter(ctx)
        agent = AgenticSearchAgent(services, ctx, emitter, metrics=metrics_service.agentic_search)

        response = await agent.run(readable_id, request, is_streaming=False)

        await guard_rail.increment(ActionType.QUERIES)

        return response
    finally:
        await services.close()


@router.post("/{readable_id}/agentic-search/stream")
async def stream_agentic_search(  # noqa: C901 - streaming orchestration is acceptable
    request: AgenticSearchRequest,
    readable_id: str = Path(..., description="The unique readable identifier of the collection"),
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
    metrics_service: MetricsService = Inject(MetricsService),
) -> StreamingResponse:
    """Streaming agentic search endpoint using Server-Sent Events.

    Streams progress events as the agent plans, searches, and evaluates.
    Events include: planning reasoning, search stats, evaluator assessment, and final results.
    """
    if not ctx.has_feature(FeatureFlag.AGENTIC_SEARCH):
        raise HTTPException(
            status_code=403,
            detail="AGENTIC_SEARCH feature not enabled for this organization",
        )

    request_id = ctx.request_id
    ctx.logger.info(
        f"[AgenticSearchStream] Starting stream for collection '{readable_id}' id={request_id}"
    )
    ctx.logger.info(
        f"[AgenticSearchStream] Request body: query={request.query!r}, "
        f"mode={request.mode}, filter={request.filter}"
    )

    await guard_rail.is_allowed(ActionType.QUERIES)

    # Subscribe to events before starting the search
    pubsub = await core_pubsub.subscribe("agentic_search", request_id)
    emitter = AgenticSearchPubSubEmitter(request_id)

    async def _run_search() -> None:
        """Run the agentic search in background.

        All exceptions MUST be caught here to guarantee an error event is emitted
        to pubsub. Without this, event_stream() hangs forever waiting for messages
        that never arrive.

        Note: agent.run() already emits AgenticSearchErrorEvent for errors inside
        the agent loop, so we track whether the agent was reached to avoid
        emitting a duplicate error event.
        """
        services = None
        agent_reached = False
        try:
            services = await AgenticSearchServices.create(ctx, readable_id)
            agent = AgenticSearchAgent(
                services, ctx, emitter, metrics=metrics_service.agentic_search
            )
            agent_reached = True
            await agent.run(readable_id, request, is_streaming=True)
        except Exception as e:
            ctx.logger.exception(f"[AgenticSearchStream] Error in search {request_id}: {e}")
            # Only emit if agent.run() wasn't reached (it handles its own error events)
            if not agent_reached:
                try:
                    await emitter.emit(AgenticSearchErrorEvent(message=str(e)))
                except Exception:
                    ctx.logger.error(
                        f"[AgenticSearchStream] Failed to emit error event for {request_id}"
                    )
        finally:
            if services is not None:
                await services.close()

    search_task = asyncio.create_task(_run_search())

    async def event_stream():  # noqa: C901 - streaming loop is acceptable
        """Generate SSE events from PubSub messages."""
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]

                    try:
                        parsed = json.loads(data)
                        event_type = parsed.get("type", "")

                        ctx.logger.info(
                            f"[AgenticSearchStream] Yielding SSE event: type={event_type}, "
                            f"keys={list(parsed.keys())}"
                        )

                        yield f"data: {data}\n\n"

                        if event_type == "done":
                            ctx.logger.info(f"[AgenticSearchStream] Done event for {request_id}")
                            try:
                                await guard_rail.increment(ActionType.QUERIES)
                            except Exception:
                                pass
                            break

                        if event_type == "error":
                            ctx.logger.error(
                                f"[AgenticSearchStream] Error event for {request_id}: "
                                f"{parsed.get('message', '')}"
                            )
                            break

                    except json.JSONDecodeError:
                        yield f"data: {data}\n\n"

                elif message["type"] == "subscribe":
                    ctx.logger.info(
                        f"[AgenticSearchStream] Subscribed to agentic_search:{request_id}"
                    )

        except asyncio.CancelledError:
            ctx.logger.info(f"[AgenticSearchStream] Cancelled stream id={request_id}")
        except Exception as e:
            ctx.logger.error(f"[AgenticSearchStream] Error id={request_id}: {e}")
            error_data = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {error_data}\n\n"
        finally:
            if not search_task.done():
                search_task.cancel()
                try:
                    await search_task
                except Exception:
                    pass
            try:
                await pubsub.close()
                ctx.logger.info(
                    f"[AgenticSearchStream] Closed pubsub for agentic_search:{request_id}"
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
