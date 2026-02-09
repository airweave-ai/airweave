"""Event emitter for spotlight search.

Allows the agent to emit progress events during search execution.
Uses a Protocol so the agent is decoupled from the transport mechanism.
"""

from typing import Protocol, Union

from airweave.api.context import ApiContext
from airweave.search.spotlight.schemas.events import (
    SpotlightDoneEvent,
    SpotlightErrorEvent,
    SpotlightEvaluatingEvent,
    SpotlightPlanningEvent,
    SpotlightSearchingEvent,
)

# Concrete union for type hints (matches SpotlightEvent but avoids Annotated issues in Protocol)
_EventTypes = Union[
    SpotlightPlanningEvent,
    SpotlightSearchingEvent,
    SpotlightEvaluatingEvent,
    SpotlightDoneEvent,
    SpotlightErrorEvent,
]


class SpotlightEmitter(Protocol):
    """Protocol for spotlight event emitters."""

    async def emit(self, event: _EventTypes) -> None:
        """Emit an event."""
        ...


class SpotlightLoggingEmitter:
    """Emits events to the logger (for non-streaming calls).

    Logs reasoning at INFO level so the agent's thought process
    is visible in logs even without streaming.
    """

    def __init__(self, ctx: ApiContext) -> None:
        """Initialize with API context for logging."""
        self._ctx = ctx

    async def emit(self, event: _EventTypes) -> None:
        """Log the event."""
        prefix = "[Spotlight:Event]"

        if isinstance(event, SpotlightPlanningEvent):
            self._ctx.logger.info(
                f"{prefix} Planning (iter {event.iteration}): {event.plan.reasoning}"
            )
        elif isinstance(event, SpotlightSearchingEvent):
            self._ctx.logger.info(
                f"{prefix} Search (iter {event.iteration}): "
                f"{event.result_count} results in {event.duration_ms}ms"
            )
        elif isinstance(event, SpotlightEvaluatingEvent):
            ev = event.evaluation
            self._ctx.logger.info(f"{prefix} Evaluation (iter {event.iteration}): {ev.reasoning}")
        elif isinstance(event, SpotlightDoneEvent):
            result_count = len(event.response.results)
            self._ctx.logger.info(f"{prefix} Done: {result_count} results")
        elif isinstance(event, SpotlightErrorEvent):
            self._ctx.logger.error(f"{prefix} Error: {event.message}")


class SpotlightPubSubEmitter:
    """Emits events via Redis PubSub for SSE streaming."""

    def __init__(self, request_id: str) -> None:
        """Initialize with request ID for the PubSub channel."""
        self._request_id = request_id

    async def emit(self, event: _EventTypes) -> None:
        """Publish event to Redis PubSub channel."""
        from airweave.core.pubsub import core_pubsub

        await core_pubsub.publish(
            "spotlight",
            self._request_id,
            event.model_dump(mode="json"),
        )


class SpotlightNoOpEmitter:
    """Does nothing -- for testing or when events aren't needed."""

    async def emit(self, event: _EventTypes) -> None:
        """No-op."""
        pass
