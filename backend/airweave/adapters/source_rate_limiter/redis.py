"""Redis-backed source rate limiter using sliding window (sorted sets + Lua).

Prevents Airweave from exhausting customer API quotas by enforcing adjusted
rate limits on external source API calls. Supports both org-level (e.g., Google Drive)
and connection-level (e.g., Notion per-user) rate limiting.

Constructor-injected Redis client; config lookups use lazy crud imports
(the adapter runs on the hot path without a caller-provided DB session).
"""

import json
import logging
import time
from typing import Any, Optional
from uuid import UUID, uuid4

from airweave.core.exceptions import SourceRateLimitExceededException
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.source_rate_limits.types import (
    PIPEDREAM_PROXY_LIMIT,
    PIPEDREAM_PROXY_WINDOW,
)

logger = logging.getLogger(__name__)

# Lua script for atomic check-and-increment.
# Returns [count, 0] on success, [-1, retry_after] when over limit.
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
        local oldest_timestamp = tonumber(oldest[2])
        retry_after = math.max(0.1, (oldest_timestamp + window_seconds) - current_time)
    end

    return {-1, retry_after}
end

redis.call('ZADD', key, current_time, unique_id)
redis.call('EXPIRE', key, expire_seconds)

return {current_count + 1, 0}
"""

KEY_PREFIX = "source_rate_limit"
CONFIG_CACHE_PREFIX = "source_rate_limit_config"
CONFIG_CACHE_TTL = 300  # 5 minutes


class RedisSourceRateLimiter:
    """Sliding-window source rate limiter backed by Redis sorted sets.

    Uses a Lua script for atomic check-and-increment to prevent race
    conditions when concurrent requests check limits simultaneously.
    """

    def __init__(self, redis_client: Any) -> None:
        """Initialize with an async Redis client instance."""
        self._redis = redis_client

    # ------------------------------------------------------------------
    # Public API (matches SourceRateLimiter protocol)
    # ------------------------------------------------------------------

    async def check_and_increment(
        self,
        org_id: UUID,
        source_short_name: str,
        source_connection_id: Optional[UUID] = None,
    ) -> None:
        """Check rate limit and increment counter if allowed.

        Reads rate_limit_level from Source table to determine counting strategy:
        - Connection-level (Notion): Tracks count per user connection
        - Org-level (Google Drive): Tracks count for entire org
        - None: No rate limiting

        Raises:
            SourceRateLimitExceededException: If rate limit is exceeded.
        """
        rate_limit_level = await self._get_source_rate_limit_level(source_short_name)

        logger.debug(
            "[SourceRateLimit] Checking: org=%s source=%s connection=%s level=%s",
            org_id,
            source_short_name,
            source_connection_id,
            rate_limit_level,
        )

        if not rate_limit_level:
            return

        limit_config = await self._get_limit_config(org_id, source_short_name)
        if not limit_config:
            return

        limit = limit_config["limit"]
        window_seconds = limit_config["window_seconds"]

        redis_key = _build_redis_key(
            org_id, source_short_name, rate_limit_level, source_connection_id
        )
        await self._lua_check_and_increment(redis_key, limit, window_seconds, source_short_name)

    async def check_pipedream_proxy_limit(self, org_id: UUID) -> None:
        """Check Pipedream proxy rate limit (configurable, defaults to 1000 req/5min).

        Raises:
            SourceRateLimitExceededException: If Pipedream proxy limit exceeded.
        """
        limit_config = await self._get_limit_config(org_id, "pipedream_proxy")

        if not limit_config:
            limit = PIPEDREAM_PROXY_LIMIT
            window_seconds = PIPEDREAM_PROXY_WINDOW
        else:
            limit = limit_config["limit"]
            window_seconds = limit_config["window_seconds"]

        redis_key = f"pipedream_proxy_rate_limit:{org_id}"
        await self._lua_check_and_increment(redis_key, limit, window_seconds, "pipedream_proxy")

    # ------------------------------------------------------------------
    # Private: Lua execution
    # ------------------------------------------------------------------

    async def _lua_check_and_increment(
        self,
        redis_key: str,
        limit: int,
        window_seconds: int,
        source_short_name: str,
    ) -> None:
        """Execute atomic Lua check-and-increment, raise on over-limit."""
        current_time = time.time()
        window_start = current_time - window_seconds
        expire_seconds = window_seconds * 2
        unique_id = str(uuid4())

        result = await self._redis.eval(
            _LUA_CHECK_AND_INCREMENT,
            1,
            redis_key,
            limit,
            window_start,
            current_time,
            window_seconds,
            expire_seconds,
            unique_id,
        )

        count_or_error = int(result[0])
        retry_after = float(result[1])

        if count_or_error == -1:
            logger.warning(
                "Source rate limit exceeded for %s: %d/%d in %ds window, retry %.2fs",
                source_short_name,
                limit,
                limit,
                window_seconds,
                retry_after,
            )
            raise SourceRateLimitExceededException(
                retry_after=retry_after,
                source_short_name=source_short_name,
            )

    # ------------------------------------------------------------------
    # Private: config / metadata lookups (lazy crud imports)
    # ------------------------------------------------------------------

    async def _get_source_rate_limit_level(self, source_short_name: str) -> Optional[str]:
        """Get rate_limit_level from Source table (Redis-cached, 10min TTL)."""
        cache_key = f"source_metadata:{source_short_name}:rate_limit_level"

        try:
            cached = await self._redis.get(cache_key)
            if cached:
                return cached if cached != "None" else None
        except Exception:
            pass

        try:
            from airweave import crud
            from airweave.db.session import get_db_context

            async with get_db_context() as db:
                source = await crud.source.get_by_short_name(db, source_short_name)
                rate_limit_level = source.rate_limit_level

                try:
                    await self._redis.setex(cache_key, 600, rate_limit_level or "None")
                except Exception:
                    pass

                return rate_limit_level

        except Exception as e:
            logger.error("Failed to fetch source metadata for %s: %s", source_short_name, e)
            return None

    async def _get_limit_config(
        self, org_id: UUID, source_short_name: str
    ) -> Optional[dict[str, Any]]:
        """Get rate limit configuration from Redis cache or database."""
        cache_key = f"{CONFIG_CACHE_PREFIX}:{org_id}:{source_short_name}"

        try:
            cached = await self._redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning("Failed to get rate limit config from cache: %s", e)

        try:
            from airweave import crud
            from airweave.db.session import get_db_context

            async with get_db_context() as db:
                rate_limit_obj = await crud.source_rate_limit.get_limit(
                    db,
                    org_id=org_id,
                    source_short_name=source_short_name,
                )

                if not rate_limit_obj:
                    try:
                        await self._redis.setex(cache_key, CONFIG_CACHE_TTL, "{}")
                    except Exception:
                        pass
                    return None

                config = {
                    "limit": rate_limit_obj.limit,
                    "window_seconds": rate_limit_obj.window_seconds,
                }

                try:
                    await self._redis.setex(cache_key, CONFIG_CACHE_TTL, json.dumps(config))
                except Exception as e:
                    logger.warning("Failed to cache rate limit config: %s", e)

                return config

        except Exception as e:
            logger.error("Failed to fetch rate limit config from database: %s", e)
            return None


# ------------------------------------------------------------------
# Module-level helpers (pure functions, no state)
# ------------------------------------------------------------------


def _build_redis_key(
    org_id: UUID,
    source_short_name: str,
    rate_limit_level: str,
    source_connection_id: Optional[UUID] = None,
) -> str:
    """Build Redis key for rate limit counting."""
    if rate_limit_level == RateLimitLevel.CONNECTION.value:
        return f"{KEY_PREFIX}:{org_id}:{source_short_name}:connection:{source_connection_id}"
    return f"{KEY_PREFIX}:{org_id}:{source_short_name}:org:org"
