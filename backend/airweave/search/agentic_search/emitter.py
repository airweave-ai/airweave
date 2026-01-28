"""Event emitter for agentic search.

Allows the agent to emit progress events to the user via SSE streaming.
"""

from typing import Any, Optional, Protocol

from pydantic import BaseModel

from airweave.api.context import ApiContext


class AgenticSearchEvent(BaseModel):
    """Event emitted by the agentic search agent.

    Simple structure: a message and optional structured data.
    """

    message: str
    data: Optional[dict[str, Any]] = None
    done: bool = False
    error: bool = False


class EventEmitter(Protocol):
    """Protocol for event emitters."""

    async def emit(self, event: AgenticSearchEvent) -> None:
        """Emit an event."""
        ...


class LoggingEmitter:
    """Emits events to the logger (for non-streaming calls)."""

    def __init__(self, ctx: ApiContext) -> None:
        """Initialize with API context for logging."""
        self._ctx = ctx

    async def emit(self, event: AgenticSearchEvent) -> None:
        """Log the event."""
        prefix = "[AgenticSearch:Event]"
        if event.error:
            self._ctx.logger.error(f"{prefix} ERROR: {event.message}")
        elif event.done:
            self._ctx.logger.info(f"{prefix} DONE: {event.message}")
        else:
            self._ctx.logger.info(f"{prefix} {event.message}")


class PubSubEmitter:
    """Emits events via Redis PubSub for SSE streaming."""

    def __init__(self, request_id: str) -> None:
        """Initialize with request ID for the PubSub channel."""
        self._request_id = request_id

    async def emit(self, event: AgenticSearchEvent) -> None:
        """Publish event to Redis PubSub channel."""
        from airweave.core.pubsub import core_pubsub

        await core_pubsub.publish(
            "agentic_search",
            self._request_id,
            event.model_dump(),
        )


class NoOpEmitter:
    """Does nothing - for testing or when events aren't needed."""

    async def emit(self, event: AgenticSearchEvent) -> None:
        """No-op."""
        pass
