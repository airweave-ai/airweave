"""Event emitter for streaming search events."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from airweave.core.protocols.pubsub import PubSub


class EventEmitter:
    """Event emitter for search operations.

    Handles publishing events to PubSub when streaming is enabled.
    All operations use this to emit lifecycle and data events.
    """

    def __init__(self, request_id: str, stream: bool, pubsub: PubSub) -> None:
        """Initialize event emitter.

        Args:
            request_id: Unique request ID for this search (always required)
            stream: Whether to actually emit events to pubsub
            pubsub: PubSub adapter for message transport

        Raises:
            ValueError: If request_id is not provided
        """
        if not request_id:
            raise ValueError("request_id is required for EventEmitter")

        self.request_id = request_id
        self.stream = stream
        self._pubsub = pubsub
        self._global_sequence = 0
        self._op_sequences: Dict[str, int] = {}

    async def emit(
        self, event_type: str, data: Optional[Dict[str, Any]] = None, op_name: Optional[str] = None
    ) -> None:
        """Emit an event to the pubsub channel if streaming is enabled.

        Args:
            event_type: Type of event (e.g., "expansion_done", "filter_applied")
            data: Event data payload
            op_name: Name of the operation emitting the event (e.g., "QueryExpansion")
        """
        if not self.stream:
            return

        # Increment sequences
        self._global_sequence += 1
        op_seq = None
        if op_name:
            self._op_sequences[op_name] = self._op_sequences.get(op_name, 0) + 1
            op_seq = self._op_sequences[op_name]

        # Build event payload
        payload: Dict[str, Any] = {
            "type": event_type,
            "seq": self._global_sequence,
            "ts": datetime.now(timezone.utc).isoformat(),
        }

        if op_name:
            payload["op"] = self._to_snake_case(op_name)
            payload["op_seq"] = op_seq

        if data:
            payload.update(data)

        # Publish to Redis channel
        try:
            await self._pubsub.publish("search", self.request_id, payload)
        except Exception:
            # Never fail pipeline due to streaming issues
            pass

    @staticmethod
    def _to_snake_case(name: str) -> str:
        """Convert operation class name to snake_case for events.

        Examples:
            QueryExpansion -> query_expansion
            EmbedQuery -> embedding
            GenerateAnswer -> completion
        """
        # Special mappings for consistency with old system
        mappings = {
            "EmbedQuery": "embedding",
            "GenerateAnswer": "completion",
            "Reranking": "llm_reranking",
            "UserFilter": "qdrant_filter",
            "Retrieval": "vector_search",
            "FederatedSearch": "federated_search",
        }

        if name in mappings:
            return mappings[name]

        # Default: convert CamelCase to snake_case
        result = []
        for i, char in enumerate(name):
            if char.isupper() and i > 0:
                result.append("_")
            result.append(char.lower())
        return "".join(result)
