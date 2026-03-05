"""PubSub protocol for realtime message fan-out to SSE consumers.

Decouples producers (sync progress relay, search emitter) from the
transport layer. The default adapter is RedisPubSub (adapters/pubsub/redis.py).
"""

from typing import Any, AsyncIterator, Protocol, runtime_checkable


@runtime_checkable
class PubSubSubscription(Protocol):
    """A single subscription handle returned by PubSub.subscribe().

    Wraps the transport-specific subscription (e.g. redis.client.PubSub)
    behind a stable interface so SSE consumers never depend on Redis directly.
    """

    def listen(self) -> AsyncIterator[dict[str, Any]]:
        """Yield messages from the subscribed channel."""
        ...

    async def close(self) -> None:
        """Release the subscription and its underlying connection."""
        ...


@runtime_checkable
class PubSub(Protocol):
    """Protocol for namespaced publish/subscribe messaging.

    Used by:
    - SyncProgressRelay: publishes sync progress snapshots
    - SSE endpoints: subscribe for real-time streaming to browsers
    - Search emitters: publish search results

    Implementations:
    - RedisPubSub — adapters/pubsub/redis.py
    - FakePubSub — adapters/pubsub/fake.py (tests)
    """

    async def publish(self, namespace: str, id_value: Any, data: Any) -> int:
        """Publish a message to a namespaced channel.

        Args:
            namespace: Logical namespace (e.g., "sync_job", "search")
            id_value: Identifier for the channel (e.g., job_id)
            data: Payload — dict (JSON-encoded by impl) or pre-encoded string

        Returns:
            Number of subscribers that received the message.
        """
        ...

    async def subscribe(self, namespace: str, id_value: Any) -> PubSubSubscription:
        """Subscribe to a namespaced channel for consuming messages.

        Args:
            namespace: Logical namespace
            id_value: Identifier for the channel

        Returns:
            A subscription handle with listen() and close() methods.
        """
        ...

    async def store_snapshot(self, key: str, data: str, ttl_seconds: int) -> None:
        """Store a point-in-time snapshot with a TTL.

        Used for operational concerns like stall detection — the snapshot
        allows external monitors to check when the last progress update was.

        Args:
            key: Storage key
            data: JSON-encoded snapshot payload
            ttl_seconds: Time-to-live in seconds
        """
        ...
