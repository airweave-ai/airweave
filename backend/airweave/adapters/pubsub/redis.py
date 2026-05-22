"""Redis-backed PubSub adapter.

Provides a namespaced publish/subscribe interface over Redis for
real-time message fan-out (SSE sync progress, search streaming, etc.).

Usage patterns:
- Namespaced channel helpers: ``make_channel("search", request_id)`` → ``search:<id>``
- High-level helpers: ``pubsub.publish("search", id, data)`` and
  ``await pubsub.subscribe("search", id)``

Notes:
- Publishes accept either strings (already JSON) or dicts which will be JSON-encoded
- Subscriptions create a dedicated Redis connection suited for long-lived SSE streams
- Both single-host and Sentinel topologies are supported transparently via
  ``airweave.core.redis_factory.make_redis_client``.
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis

from airweave.core.redis_client import redis_client
from airweave.core.redis_factory import get_socket_keepalive_options, make_redis_client


class RedisPubSub:
    """Redis-backed implementation of the PubSub protocol."""

    @staticmethod
    def make_channel(namespace: str, id_str: str) -> str:
        """Build a Redis channel name as ``<namespace>:<id>``."""
        return f"{namespace}:{id_str}"

    async def publish(self, namespace: str, id_value: Any, data: Any) -> int:
        """Publish a message to a namespaced channel.

        Args:
            namespace: The channel namespace (e.g., "search", "sync_job")
            id_value: Identifier used to build the channel name
            data: Dict payload (JSON-encoded) or string already encoded

        Returns:
            Number of subscribers that received the message
        """
        channel = self.make_channel(namespace, str(id_value))
        message = data if isinstance(data, str) else json.dumps(data)
        return await redis_client.publish(channel, message)

    async def store_snapshot(self, key: str, data: str, ttl_seconds: int) -> None:
        """Store a snapshot in Redis with a TTL (for stall detection)."""
        await redis_client.client.setex(key, ttl_seconds, data)

    async def subscribe(self, namespace: str, id_value: Any) -> redis.client.PubSub:
        """Create a dedicated pubsub connection and subscribe to a channel.

        A separate client is created for pubsub to avoid connection pool
        interference with regular Redis usage. In Sentinel mode the connection
        is bound to the current master and transparently reconnects on failover.

        Args:
            namespace: The channel namespace
            id_value: Identifier used to build the channel name

        Returns:
            A Redis ``PubSub`` instance subscribed to the channel
        """
        channel = self.make_channel(namespace, str(id_value))

        pubsub_redis = make_redis_client(
            max_connections=1,
            socket_keepalive=True,
            socket_keepalive_options=get_socket_keepalive_options(),
            socket_connect_timeout=5,
        )

        pubsub = pubsub_redis.pubsub()
        await pubsub.subscribe(channel)
        return pubsub
