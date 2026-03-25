"""Stream relay — bridges search events from EventBus to PubSub for SSE.

Subscribes to ``search.*`` on the global EventBus. Each event is serialized
to SSE-compatible JSON and published to PubSub channel
``agentic_search_v2:{request_id}``.

Stateless: no sessions needed. The request_id on each event determines
the PubSub channel. Instant/classic events also flow through but their
PubSub channels have no subscribers, so publishes are harmless no-ops.
"""

import logging
from typing import Any, List

from airweave.core.events.base import DomainEvent
from airweave.core.events.search import (
    SearchCompletedEvent,
    SearchFailedEvent,
    SearchRerankingEvent,
    SearchStartedEvent,
    SearchThinkingEvent,
    SearchToolCalledEvent,
)
from airweave.core.protocols.event_bus import EventSubscriber
from airweave.core.protocols.pubsub import PubSub

logger = logging.getLogger(__name__)

_SSE_TYPE_MAP = {
    "search.started": "started",
    "search.thinking": "thinking",
    "search.tool_called": "tool_call",
    "search.reranking": "reranking",
    "search.completed": "done",
    "search.failed": "error",
}


class SearchStreamRelay(EventSubscriber):
    """Stateless relay: search.* events -> PubSub -> SSE."""

    EVENT_PATTERNS: List[str] = ["search.*"]

    def __init__(self, pubsub: PubSub) -> None:
        """Initialize with PubSub transport."""
        self._pubsub = pubsub

    async def handle(self, event: DomainEvent) -> None:
        """Convert domain event to SSE JSON and publish to PubSub."""
        request_id = getattr(event, "request_id", None)
        if not request_id:
            return

        payload = self._build_sse_payload(event)
        if payload is None:
            return

        try:
            await self._pubsub.publish("agentic_search_v2", request_id, payload)
        except Exception as e:
            logger.error(
                "SearchStreamRelay: failed to publish %s for %s: %s",
                event.event_type,
                request_id,
                e,
            )

    def _build_sse_payload(self, event: DomainEvent) -> dict[str, Any] | None:
        """Build SSE JSON payload from a domain event."""
        sse_type = _SSE_TYPE_MAP.get(event.event_type.value)
        if sse_type is None:
            logger.warning(
                "SearchStreamRelay: unknown event type %s",
                event.event_type,
            )
            return None

        payload: dict[str, Any] = {"type": sse_type}

        if isinstance(event, SearchStartedEvent):
            payload["request_id"] = event.request_id
            payload["tier"] = event.tier
            payload["collection_readable_id"] = event.collection_readable_id

        elif isinstance(event, SearchThinkingEvent):
            payload["thinking"] = event.thinking
            payload["text"] = event.text
            payload["duration_ms"] = event.duration_ms
            payload["diagnostics"] = event.diagnostics.model_dump()

        elif isinstance(event, SearchToolCalledEvent):
            payload["tool_name"] = event.tool_name
            payload["duration_ms"] = event.duration_ms
            payload["diagnostics"] = event.diagnostics.model_dump()

        elif isinstance(event, SearchRerankingEvent):
            payload["duration_ms"] = event.duration_ms
            payload["diagnostics"] = event.diagnostics.model_dump()

        elif isinstance(event, SearchCompletedEvent):
            payload["results"] = event.results  # already serialized dicts
            payload["duration_ms"] = event.duration_ms
            if event.diagnostics:
                payload["diagnostics"] = event.diagnostics.model_dump()

        elif isinstance(event, SearchFailedEvent):
            payload["message"] = event.message
            payload["error_category"] = event.error_category
            payload["duration_ms"] = event.duration_ms
            if event.diagnostics:
                payload["diagnostics"] = event.diagnostics.model_dump()

        return payload
