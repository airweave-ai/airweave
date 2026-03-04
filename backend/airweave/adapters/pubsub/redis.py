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
"""

from __future__ import annotations

import json
import platform
from typing import Any

import redis.asyncio as redis

from airweave.core.config import settings
from airweave.core.redis_client import redis_client


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
        interference with regular Redis usage.

        Args:
            namespace: The channel namespace
            id_value: Identifier used to build the channel name

        Returns:
            A Redis ``PubSub`` instance subscribed to the channel
        """
        channel = self.make_channel(namespace, str(id_value))

        if settings.REDIS_PASSWORD:
            from urllib.parse import quote

            encoded_pwd = quote(settings.REDIS_PASSWORD, safe="")
            redis_url = (
                f"redis://:{encoded_pwd}@{settings.REDIS_HOST}:"
                f"{settings.REDIS_PORT}/{settings.REDIS_DB}"
            )
        else:
            redis_url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"

        if platform.system() == "Darwin":
            socket_keepalive_options = {}
        else:
            import socket

            if hasattr(socket, "TCP_KEEPIDLE"):
                socket_keepalive_options = {
                    socket.TCP_KEEPIDLE: 60,
                    socket.TCP_KEEPINTVL: 10,
                    socket.TCP_KEEPCNT: 6,
                }
            else:
                socket_keepalive_options = {}

        pubsub_redis = await redis.from_url(
            redis_url,
            decode_responses=True,
            socket_keepalive=True,
            socket_connect_timeout=5,
            socket_keepalive_options=socket_keepalive_options,
        )

        pubsub = pubsub_redis.pubsub()
        await pubsub.subscribe(channel)
        return pubsub
