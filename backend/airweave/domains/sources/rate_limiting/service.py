"""Source rate limiter — distributed sliding-window enforcement via Redis.

Prevents Airweave from exhausting customer API quotas by transparently
throttling external source API calls. The AirweaveHttpClient calls
``check_and_increment`` before every request; if the limit is exceeded
it raises ``InternalRateLimitExceeded`` which the client converts
to a synthetic 429 so the source's retry logic handles it naturally.

Architecture:
- **Config** (limit + window_seconds) is persisted in the DB per org+source.
- **Counting** (sliding window sorted set) is ephemeral in Redis.
- The config is cached in Redis for 5 min via ``RateLimitConfigProvider``.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

import redis.asyncio as aioredis

from airweave.core.logging import logger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.sources.rate_limiting.exceptions import InternalRateLimitExceeded

if TYPE_CHECKING:
    from airweave.domains.sources.protocols import SourceRegistryProtocol
    from airweave.domains.sources.rate_limiting.protocols import RateLimitConfigProvider

_METADATA_CACHE_TTL = 600
_KEY_PREFIX = "source_rate_limit"

_LUA_CHECK_AND_INCREMENT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window_start = tonumber(ARGV[2])
local current_time = tonumber(ARGV[3])
local window_seconds = tonumber(ARGV[4])
local expire_seconds = tonumber(ARGV[5])
local unique_id = ARGV[6]

redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
local current_count = redis.call('ZCOUNT', key, window_start, current_time)

if current_count >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = window_seconds
    if oldest and oldest[2] then
        retry_after = math.max(0.1, tonumber(oldest[2]) + window_seconds - current_time)
    end
    return {-1, retry_after}
end

redis.call('ZADD', key, current_time, unique_id)
redis.call('EXPIRE', key, expire_seconds)
return {current_count + 1, 0}
"""


class SourceRateLimiter:
    """Distributed source rate limiter using Redis sliding-window algorithm.

    All dependencies are injected — no global singletons.
    """

    def __init__(
        self,
        redis: aioredis.Redis,
        source_registry: SourceRegistryProtocol,
        config_provider: RateLimitConfigProvider,
    ) -> None:
        """Initialize with Redis client, source registry, and config provider."""
        self._redis = redis
        self._source_registry = source_registry
        self._config_provider = config_provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check_and_increment(
        self,
        org_id: UUID,
        source_short_name: str,
        source_connection_id: Optional[UUID] = None,
    ) -> None:
        """Check rate limit and increment counter atomically.

        Raises:
            InternalRateLimitExceeded: If rate limit is exceeded.
        """
        level = await self._get_rate_limit_level(source_short_name)
        if not level:
            return

        config = await self._config_provider.get_config(org_id, source_short_name)
        if not config:
            return

        limit = config.limit
        window_seconds = config.window_seconds
        redis_key = self._build_key(org_id, source_short_name, level, source_connection_id)

        now = time.time()
        result = await self._redis.eval(
            _LUA_CHECK_AND_INCREMENT,
            1,
            redis_key,
            limit,
            now - window_seconds,
            now,
            window_seconds,
            window_seconds * 2,
            str(uuid4()),
        )

        count_or_error = int(result[0])
        retry_after = float(result[1])

        if count_or_error == -1:
            logger.warning(
                f"Source rate limit exceeded for {source_short_name}: "
                f"{limit}/{limit} in {window_seconds}s, retry after {retry_after:.2f}s"
            )
            raise InternalRateLimitExceeded(
                retry_after=retry_after,
                source_short_name=source_short_name,
            )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _get_rate_limit_level(self, source_short_name: str) -> Optional[str]:
        """Look up rate_limit_level from source registry, cached in Redis."""
        cache_key = f"source_metadata:{source_short_name}:rate_limit_level"

        try:
            cached = await self._redis.get(cache_key)
            if cached:
                return cached if cached != "None" else None
        except Exception:
            pass

        try:
            entry = self._source_registry.get(source_short_name)
            level = entry.rate_limit_level
            try:
                await self._redis.setex(cache_key, _METADATA_CACHE_TTL, level or "None")
            except Exception:
                pass
            return level
        except KeyError:
            return None

    @staticmethod
    def _build_key(
        org_id: UUID,
        source_short_name: str,
        level: str,
        source_connection_id: Optional[UUID] = None,
    ) -> str:
        """Build the Redis sorted-set key for rate limit counting."""
        if level == RateLimitLevel.CONNECTION.value:
            return f"{_KEY_PREFIX}:{org_id}:{source_short_name}:connection:{source_connection_id}"
        return f"{_KEY_PREFIX}:{org_id}:{source_short_name}:org:org"
