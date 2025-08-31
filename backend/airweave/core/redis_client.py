"""Redis client configuration."""

import platform
import socket
from typing import Optional

import redis.asyncio as redis

from airweave.core.config import settings
from airweave.core.logging import logger


class RedisClient:
    """Redis client wrapper with connection pooling."""

    def __init__(self):
        """Initialize Redis clients with separate pools."""
        self._client: Optional[redis.Redis] = None
        self._pubsub_client: Optional[redis.Redis] = None
        self._enabled = settings.REDIS_MONITORING_ENABLED

    @property
    def client(self) -> redis.Redis:
        """Get or create the main Redis client."""
        if not self._enabled:
            raise RuntimeError("Redis monitoring is disabled in this deployment")
        if self._client is None:
            self._client = self._create_client(max_connections=50)
        return self._client

    @property
    def pubsub_client(self) -> redis.Redis:
        """Get or create the pubsub Redis client for SSE."""
        if not self._enabled:
            raise RuntimeError("Redis monitoring is disabled in this deployment")
        if self._pubsub_client is None:
            self._pubsub_client = self._create_client(max_connections=100)
        return self._pubsub_client

    def _get_socket_keepalive_options(self) -> dict:
        """Get socket keepalive options based on the OS.

        Returns empty dict for macOS to avoid socket option errors.
        Returns proper TCP keepalive settings for Linux.
        """
        if platform.system() == "Darwin":  # macOS
            return {}
        else:  # Linux and others
            # Use the correct Linux TCP keepalive constants
            # TCP_KEEPIDLE = 4
            # TCP_KEEPINTVL = 5
            # TCP_KEEPCNT = 6

            if hasattr(socket, "TCP_KEEPIDLE"):
                return {
                    socket.TCP_KEEPIDLE: 60,  # Start keepalive after 60s idle
                    socket.TCP_KEEPINTVL: 10,  # Interval between keepalive probes
                    socket.TCP_KEEPCNT: 6,  # Number of keepalive probes
                }
            else:
                # Fallback for systems without these constants
                return {}

    def _create_client(self, max_connections: int = 50) -> redis.Redis:
        """Create a Redis client with specified connection pool size."""
        # Create connection pool with proper configuration
        pool = redis.ConnectionPool(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
            decode_responses=True,
            max_connections=max_connections,
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options=self._get_socket_keepalive_options(),
            socket_connect_timeout=5,  # Add connection timeout
            socket_timeout=5,  # Add socket timeout
            retry_on_error=[ConnectionError, TimeoutError],  # Retry on these errors
        )

        return redis.Redis(connection_pool=pool)

    async def publish(self, channel: str, message: str) -> int:
        """Publish a message to a channel.

        Args:
            channel: The channel to publish to
            message: The message to publish

        Returns:
            The number of subscribers that received the message
        """
        if not self._enabled:
            logger.debug(f"Redis monitoring disabled - skipping publish to channel: {channel}")
            return 0
        return await self.client.publish(channel, message)

    async def test_connection(self) -> bool:
        """Test Redis connection.

        Returns:
            True if connection is successful, False otherwise
        """
        if not self._enabled:
            logger.info("Redis monitoring disabled - skipping connection test")
            return True
        try:
            await self.client.ping()
            logger.info("Redis connection successful")
            return True
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            return False

    async def close(self) -> None:
        """Close Redis connection gracefully."""
        if not self._enabled:
            logger.debug("Redis monitoring disabled - skipping connection close")
            return
        if self._client:
            await self._client.close()
        if self._pubsub_client:
            await self._pubsub_client.close()

    @property
    def is_enabled(self) -> bool:
        """Check if Redis monitoring is enabled.
        
        Returns:
            True if Redis monitoring is enabled, False otherwise
        """
        return self._enabled

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set a key-value pair in Redis.
        
        Args:
            key: The key to set
            value: The value to set
            ex: Optional expiration time in seconds
            
        Returns:
            True if successful, False if Redis is disabled
        """
        if not self._enabled:
            logger.debug(f"Redis monitoring disabled - skipping set operation for key: {key}")
            return False
        return await self.client.set(key, value, ex=ex)

    async def get(self, key: str) -> Optional[str]:
        """Get a value from Redis.
        
        Args:
            key: The key to get
            
        Returns:
            The value if found and Redis is enabled, None otherwise
        """
        if not self._enabled:
            logger.debug(f"Redis monitoring disabled - skipping get operation for key: {key}")
            return None
        return await self.client.get(key)

    async def delete(self, key: str) -> int:
        """Delete a key from Redis.
        
        Args:
            key: The key to delete
            
        Returns:
            Number of keys deleted (0 if Redis is disabled)
        """
        if not self._enabled:
            logger.debug(f"Redis monitoring disabled - skipping delete operation for key: {key}")
            return 0
        return await self.client.delete(key)


# Create a global instance
redis_client = RedisClient()
