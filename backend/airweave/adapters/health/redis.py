"""Redis health probe adapter."""

import time

from redis.asyncio import Redis

from airweave.core.health.protocols import HealthProbe
from airweave.schemas.health import CheckStatus, DependencyCheck


class RedisHealthProbe(HealthProbe):
    """Probes Redis by sending a ``PING`` command."""

    def __init__(self, client: Redis) -> None:
        """Initialize RedisHealthProbe with the given async Redis client."""
        self._client = client

    @property
    def name(self) -> str:
        """Return the probe name for this health check."""
        return "redis"

    async def check(self) -> DependencyCheck:
        """Send a PING command and return the health status."""
        start = time.perf_counter()
        await self._client.ping()
        latency = (time.perf_counter() - start) * 1000
        return DependencyCheck(status=CheckStatus.up, latency_ms=round(latency, 2))
