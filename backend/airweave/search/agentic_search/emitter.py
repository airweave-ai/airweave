"""Event emitter for agentic search.

Allows the agent to emit progress events during search execution.
Uses a Protocol so the agent is decoupled from the transport mechanism.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Union

if TYPE_CHECKING:
    from airweave.core.protocols.pubsub import PubSub

from airweave.api.context import ApiContext
from airweave.search.agentic_search.schemas.events import (
    AgenticSearchDoneEvent,
    AgenticSearchErrorEvent,
    AgenticSearchEvaluatingEvent,
    AgenticSearchingEvent,
    AgenticSearchPlanningEvent,
)

# Concrete union for type hints (matches AgenticSearchEvent but avoids Annotated issues in Protocol)
_EventTypes = Union[
    AgenticSearchPlanningEvent,
    AgenticSearchingEvent,
    AgenticSearchEvaluatingEvent,
    AgenticSearchDoneEvent,
    AgenticSearchErrorEvent,
]


class AgenticSearchEmitter(Protocol):
    """Protocol for agentic_search event emitters."""

    async def emit(self, event: _EventTypes) -> None:
        """Emit an event."""
        ...


class AgenticSearchLoggingEmitter:
    """Emits events to the logger (for non-streaming calls).

    Logs reasoning at INFO level so the agent's thought process
    is visible in logs even without streaming.
    """

    def __init__(self, ctx: ApiContext) -> None:
        """Initialize with API context for logging."""
        self._ctx = ctx

    async def emit(self, event: _EventTypes) -> None:
        """Log the event."""
        prefix = "[AgenticSearch:Event]"

        if isinstance(event, AgenticSearchPlanningEvent):
            self._ctx.logger.debug(
                f"{prefix} Planning (iter {event.iteration}): {event.plan.reasoning}"
            )
        elif isinstance(event, AgenticSearchingEvent):
            self._ctx.logger.debug(
                f"{prefix} Search (iter {event.iteration}): "
                f"{event.result_count} results in {event.duration_ms}ms"
            )
        elif isinstance(event, AgenticSearchEvaluatingEvent):
            ev = event.evaluation
            self._ctx.logger.debug(f"{prefix} Evaluation (iter {event.iteration}): {ev.reasoning}")
        elif isinstance(event, AgenticSearchDoneEvent):
            result_count = len(event.response.results)
            self._ctx.logger.debug(f"{prefix} Done: {result_count} results")
        elif isinstance(event, AgenticSearchErrorEvent):
            self._ctx.logger.error(f"{prefix} Error: {event.message}")


class AgenticSearchPubSubEmitter:
    """Emits events via PubSub for SSE streaming."""

    def __init__(self, request_id: str, *, pubsub: "PubSub") -> None:
        """Initialize with request ID and PubSub adapter."""
        self._request_id = request_id
        self._pubsub = pubsub

    async def emit(self, event: _EventTypes) -> None:
        """Publish event to the PubSub channel."""
        await self._pubsub.publish(
            "agentic_search",
            self._request_id,
            event.model_dump(mode="json"),
        )


class AgenticSearchNoOpEmitter:
    """Does nothing -- for testing or when events aren't needed."""

    async def emit(self, event: _EventTypes) -> None:
        """No-op."""
        pass
