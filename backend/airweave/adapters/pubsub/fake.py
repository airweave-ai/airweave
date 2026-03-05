"""Fake PubSub adapter for testing.

Records all published messages and subscriptions for assertions
without requiring a real Redis connection.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, AsyncIterator


class FakePubSubSubscription:
    """In-memory subscription handle satisfying PubSubSubscription protocol."""

    def listen(self) -> AsyncIterator[dict[str, Any]]:
        return _empty_listen()

    async def close(self) -> None:
        pass


class FakePubSub:
    """Test implementation of the PubSub protocol.

    Tracks published messages and snapshots in memory.

    Usage:
        fake = FakePubSub()
        await some_service(pubsub=fake)

        assert fake.published[("search", "req-123")] == [{"type": "done"}]
    """

    def __init__(self) -> None:
        """Initialize empty recording state."""
        self.published: dict[tuple[str, str], list[Any]] = defaultdict(list)
        self.snapshots: dict[str, tuple[str, int]] = {}
        self.subscriptions: list[tuple[str, str]] = []

    async def publish(self, namespace: str, id_value: Any, data: Any) -> int:
        """Record a published message and return 1."""
        key = (namespace, str(id_value))
        self.published[key].append(data)
        return 1

    async def subscribe(self, namespace: str, id_value: Any) -> FakePubSubSubscription:
        """Record a subscription and return a no-op subscription handle."""
        self.subscriptions.append((namespace, str(id_value)))
        return FakePubSubSubscription()

    async def store_snapshot(self, key: str, data: str, ttl_seconds: int) -> None:
        """Record a snapshot with its TTL."""
        self.snapshots[key] = (data, ttl_seconds)

    def clear(self) -> None:
        """Reset all recorded state."""
        self.published.clear()
        self.snapshots.clear()
        self.subscriptions.clear()


async def _empty_listen() -> AsyncIterator[dict[str, Any]]:
    """Yield nothing -- placeholder for listen() in tests."""
    return
    yield  # noqa: RET504 -- makes this an async generator
