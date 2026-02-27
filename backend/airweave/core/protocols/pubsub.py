"""PubSub protocol for realtime message fan-out to SSE consumers.

Decouples producers (sync progress relay, search emitter) from the
transport layer. The default adapter is RedisPubSub (adapters/pubsub/redis.py).
"""

from typing import Any, AsyncIterator, Protocol, runtime_checkable


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

    async def subscribe(self, namespace: str, id_value: Any) -> AsyncIterator:
        """Subscribe to a namespaced channel for consuming messages.

        Args:
            namespace: Logical namespace
            id_value: Identifier for the channel

        Returns:
            An async iterator that yields messages.
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
