"""Spotlight search endpoints.

These endpoints provide agentic search capabilities using the spotlight module.
The spotlight module creates its own database connection based on its config,
completely separate from the Airweave API's database connection.
"""

import asyncio
import json

from fastapi import Depends, Path
from starlette.responses import StreamingResponse

from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.router import TrailingSlashRouter
from airweave.core.guard_rail_service import GuardRailService
from airweave.core.pubsub import core_pubsub
from airweave.core.shared_models import ActionType
from airweave.search.spotlight.core.agent import SpotlightAgent
from airweave.search.spotlight.emitter import (
    SpotlightLoggingEmitter,
    SpotlightPubSubEmitter,
)
from airweave.search.spotlight.schemas import SpotlightRequest, SpotlightResponse
from airweave.search.spotlight.services import SpotlightServices

router = TrailingSlashRouter()


@router.post("/{readable_id}/spotlight/search", response_model=SpotlightResponse)
async def spotlight_search(
    request: SpotlightRequest,
    readable_id: str = Path(..., description="The unique readable identifier of the collection"),
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
) -> SpotlightResponse:
    """Spotlight agentic search."""
    await guard_rail.is_allowed(ActionType.QUERIES)

    services = await SpotlightServices.create(ctx, readable_id)

    try:
        emitter = SpotlightLoggingEmitter(ctx)
        agent = SpotlightAgent(services, ctx, emitter)

        response = await agent.run(readable_id, request)

        await guard_rail.increment(ActionType.QUERIES)

        return response
    finally:
        await services.close()


@router.post("/{readable_id}/spotlight/search/stream")
async def stream_spotlight_search(  # noqa: C901 - streaming orchestration is acceptable
    request: SpotlightRequest,
    readable_id: str = Path(..., description="The unique readable identifier of the collection"),
    ctx: ApiContext = Depends(deps.get_context),
    guard_rail: GuardRailService = Depends(deps.get_guard_rail_service),
) -> StreamingResponse:
    """Streaming spotlight search endpoint using Server-Sent Events.

    Streams progress events as the agent plans, searches, and evaluates.
    Events include: planning reasoning, search stats, evaluator assessment, and final results.
    """
    request_id = ctx.request_id
    ctx.logger.info(
        f"[SpotlightStream] Starting stream for collection '{readable_id}' id={request_id}"
    )

    await guard_rail.is_allowed(ActionType.QUERIES)

    # Subscribe to events before starting the search
    pubsub = await core_pubsub.subscribe("spotlight", request_id)
    emitter = SpotlightPubSubEmitter(request_id)

    async def _run_search() -> None:
        """Run the spotlight search in background."""
        services = await SpotlightServices.create(ctx, readable_id)
        try:
            agent = SpotlightAgent(services, ctx, emitter)
            await agent.run(readable_id, request)
        except Exception as e:
            ctx.logger.exception(f"[SpotlightStream] Error in search {request_id}: {e}")
        finally:
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

                        yield f"data: {data}\n\n"

                        if event_type == "done":
                            ctx.logger.info(f"[SpotlightStream] Done event for {request_id}")
                            try:
                                await guard_rail.increment(ActionType.QUERIES)
                            except Exception:
                                pass
                            break

                        if event_type == "error":
                            ctx.logger.error(
                                f"[SpotlightStream] Error event for {request_id}: "
                                f"{parsed.get('message', '')}"
                            )
                            break

                    except json.JSONDecodeError:
                        yield f"data: {data}\n\n"

                elif message["type"] == "subscribe":
                    ctx.logger.info(f"[SpotlightStream] Subscribed to spotlight:{request_id}")

        except asyncio.CancelledError:
            ctx.logger.info(f"[SpotlightStream] Cancelled stream id={request_id}")
        except Exception as e:
            ctx.logger.error(f"[SpotlightStream] Error id={request_id}: {e}")
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
                ctx.logger.info(f"[SpotlightStream] Closed pubsub for spotlight:{request_id}")
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
