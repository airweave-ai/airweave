"""Fake PubSub adapter for testing.

Records all published messages and subscriptions for assertions
without requiring a real Redis connection.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, AsyncIterator


class FakePubSubSubscription:
    """In-memory subscription handle satisfying PubSubSubscription protocol.

    Supports canned messages and optional error injection for testing
    SSE consumer code paths (message forwarding, error handling, close errors).
    """

    def __init__(
        self,
        messages: list[dict[str, Any]] | None = None,
        listen_error: BaseException | None = None,
        close_error: Exception | None = None,
    ) -> None:
        self._messages = messages or []
        self._listen_error = listen_error
        self._close_error = close_error

    def listen(self) -> AsyncIterator[dict[str, Any]]:
        return _fake_listen(self._messages, self._listen_error)

    async def close(self) -> None:
        if self._close_error:
            raise self._close_error


class FakePubSub:
    """Test implementation of the PubSub protocol.

    Tracks published messages and snapshots in memory.

    Usage:
        fake = FakePubSub()
        await some_service(pubsub=fake)

        assert fake.published[("search", "req-123")] == [{"type": "done"}]

    To inject messages into SSE consumers::

        fake.queued_messages = [{"type": "message", "data": '{"x":1}'}]
    """

    def __init__(self) -> None:
        """Initialize empty recording state."""
        self.published: dict[tuple[str, str], list[Any]] = defaultdict(list)
        self.snapshots: dict[str, tuple[str, int]] = {}
        self.subscriptions: list[tuple[str, str]] = []
        self.queued_messages: list[dict[str, Any]] = []
        self.listen_error: BaseException | None = None
        self.close_error: Exception | None = None

    async def publish(self, namespace: str, id_value: Any, data: Any) -> int:
        """Record a published message and return 1."""
        key = (namespace, str(id_value))
        self.published[key].append(data)
        return 1

    async def subscribe(self, namespace: str, id_value: Any) -> FakePubSubSubscription:
        """Record a subscription and return a subscription handle."""
        self.subscriptions.append((namespace, str(id_value)))
        return FakePubSubSubscription(
            messages=list(self.queued_messages),
            listen_error=self.listen_error,
            close_error=self.close_error,
        )

    async def store_snapshot(self, key: str, data: str, ttl_seconds: int) -> None:
        """Record a snapshot with its TTL."""
        self.snapshots[key] = (data, ttl_seconds)

    def clear(self) -> None:
        """Reset all recorded state."""
        self.published.clear()
        self.snapshots.clear()
        self.subscriptions.clear()
        self.queued_messages.clear()
        self.listen_error = None
        self.close_error = None


async def _fake_listen(
    messages: list[dict[str, Any]],
    error: BaseException | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield canned messages, then optionally raise."""
    for msg in messages:
        yield msg
    if error:
        raise error
