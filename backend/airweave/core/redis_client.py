"""Redis client configuration."""

from typing import Optional

import redis.asyncio as redis

from airweave.core.logging import logger
from airweave.core.redis_factory import get_socket_keepalive_options, make_redis_client


class RedisClient:
    """Redis client wrapper with connection pooling."""

    def __init__(self):
        """Initialize Redis clients with separate pools."""
        self._client: Optional[redis.Redis] = None
        self._pubsub_client: Optional[redis.Redis] = None

    @property
    def client(self) -> redis.Redis:
        """Get or create the main Redis client."""
        if self._client is None:
            self._client = self._create_client(max_connections=50)
        return self._client

    @property
    def pubsub_client(self) -> redis.Redis:
        """Get or create the pubsub Redis client for SSE."""
        if self._pubsub_client is None:
            self._pubsub_client = self._create_client(max_connections=100)
        return self._pubsub_client

    def _create_client(self, max_connections: int = 50) -> redis.Redis:
        """Create a Redis client using the shared factory.

        Honours single-host vs. Sentinel mode based on settings — see
        ``airweave.core.redis_factory.make_redis_client``.
        """
        return make_redis_client(
            max_connections=max_connections,
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options=get_socket_keepalive_options(),
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_error=[ConnectionError, TimeoutError],
        )

    async def publish(self, channel: str, message: str) -> int:
        """Publish a message to a channel.

        Args:
            channel: The channel to publish to
            message: The message to publish

        Returns:
            The number of subscribers that received the message
        """
        return await self.client.publish(channel, message)

    async def test_connection(self) -> bool:
        """Test Redis connection.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            await self.client.ping()
            logger.info("Redis connection successful")
            return True
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            return False

    async def close(self) -> None:
        """Close Redis connection gracefully."""
        if self._client:
            await self._client.close()
        if self._pubsub_client:
            await self._pubsub_client.close()


# Create a global instance
redis_client = RedisClient()
