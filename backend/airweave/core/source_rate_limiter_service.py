"""Source rate limiter service using Redis for distributed rate limiting.

Prevents Airweave from exhausting customer API quotas by enforcing adjusted
rate limits on external source API calls. Supports both org-level (e.g., Google Drive)
and connection-level (e.g., Notion per-user) rate limiting.
"""

import time
from typing import Optional
from uuid import UUID

from airweave.core.exceptions import SourceRateLimitExceededException
from airweave.core.logging import logger
from airweave.core.redis_client import redis_client
from airweave.core.shared_models import RateLimitLevel


class SourceRateLimiter:
    """Distributed source rate limiter using Redis sliding window algorithm.

    Enforces rate limits on external source API calls across horizontally scaled instances.
    Counts stored in Redis sorted sets, configurations cached from database.

    Uses Lua scripts for atomic check-and-increment operations to prevent race conditions
    when concurrent requests check limits simultaneously.
    """

    # Redis key prefixes
    KEY_PREFIX = "source_rate_limit"
    CONFIG_CACHE_PREFIX = "source_rate_limit_config"
    CONFIG_CACHE_TTL = 300  # 5 minutes

    # Lua script for atomic check-and-increment
    # Returns: current_count if allowed, -1 if over limit
    # If over limit, also returns retry_after as second return value
    LUA_CHECK_AND_INCREMENT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window_start = tonumber(ARGV[2])
local current_time = tonumber(ARGV[3])
local window_seconds = tonumber(ARGV[4])
local expire_seconds = tonumber(ARGV[5])
local unique_id = ARGV[6]  -- UUID to make each entry unique

-- Remove old entries outside sliding window
redis.call('ZREMRANGEBYSCORE', key, 0, window_start)

-- Count current requests in window
local current_count = redis.call('ZCOUNT', key, window_start, current_time)

-- Check if over limit
if current_count >= limit then
    -- Get oldest entry to calculate retry_after
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = window_seconds  -- Default

    if oldest and oldest[2] then
        local oldest_timestamp = tonumber(oldest[2])
        retry_after = math.max(0.1, (oldest_timestamp + window_seconds) - current_time)
    end

    return {-1, retry_after}  -- Over limit, return retry_after
end

-- Add current request to sliding window with unique member
-- Score = current_time (for range queries)
-- Member = unique_id (ensures uniqueness for concurrent requests at same time)
redis.call('ZADD', key, current_time, unique_id)

-- Set expiration for auto-cleanup
redis.call('EXPIRE', key, expire_seconds)

return {current_count + 1, 0}  -- Success, return new count
"""

    @staticmethod
    async def _get_source_rate_limit_level(source_short_name: str) -> Optional[str]:
        """Get rate_limit_level from Source table (cached).

        Args:
            source_short_name: Source identifier

        Returns:
            "org", "connection", or None if source doesn't use rate limiting
        """
        cache_key = f"source_metadata:{source_short_name}:rate_limit_level"

        # Try cache first
        try:
            cached = await redis_client.client.get(cache_key)
            if cached:
                return cached if cached != "None" else None
        except Exception:
            pass

        # Cache miss - fetch from database
        try:
            from airweave import crud
            from airweave.db.session import get_db_context

            async with get_db_context() as db:
                source = await crud.source.get_by_short_name(db, source_short_name)
                rate_limit_level = source.rate_limit_level

                # Cache for 10 minutes (source metadata rarely changes)
                try:
                    await redis_client.client.setex(cache_key, 600, rate_limit_level or "None")
                except Exception:
                    pass

                return rate_limit_level

        except Exception as e:
            logger.error(f"Failed to fetch source metadata for {source_short_name}: {e}")
            return None

    @staticmethod
    def _get_redis_key(
        org_id: UUID,
        source_short_name: str,
        rate_limit_level: str,
        source_connection_id: Optional[UUID] = None,
    ) -> str:
        """Build Redis key for rate limit counting.

        Format: source_rate_limit:{org_id}:{source_short_name}:{level}:{id}
        - Org-level: source_rate_limit:{org_id}:google_drive:org:org
        - Connection-level: source_rate_limit:{org_id}:notion:connection:{connection_id}

        Args:
            org_id: Organization ID
            source_short_name: Source identifier
            rate_limit_level: "org" or "connection" (from Source table)
            source_connection_id: Connection ID (for connection-level)

        Returns:
            Redis key string
        """
        if rate_limit_level == RateLimitLevel.CONNECTION.value:
            return (
                f"{SourceRateLimiter.KEY_PREFIX}:{org_id}:{source_short_name}:"
                f"connection:{source_connection_id}"
            )
        else:  # RateLimitLevel.ORG
            return f"{SourceRateLimiter.KEY_PREFIX}:{org_id}:{source_short_name}:org:org"

    @staticmethod
    def _get_config_cache_key(
        org_id: UUID,
        source_short_name: str,
    ) -> str:
        """Build cache key for rate limit configuration.

        Args:
            org_id: Organization ID
            source_short_name: Source identifier

        Returns:
            Cache key string
        """
        return f"{SourceRateLimiter.CONFIG_CACHE_PREFIX}:{org_id}:{source_short_name}"

    @staticmethod
    async def _get_limit_config(
        org_id: UUID,
        source_short_name: str,
    ) -> Optional[dict]:
        """Get rate limit configuration from cache or database.

        Gets ONE limit that applies to all users/connections of this source
        in the organization.

        Args:
            org_id: Organization ID
            source_short_name: Source identifier

        Returns:
            Dict with 'limit' and 'window_seconds' if configured, None otherwise
        """
        cache_key = SourceRateLimiter._get_config_cache_key(org_id, source_short_name)

        # Try cache first
        try:
            cached = await redis_client.client.get(cache_key)
            if cached:
                import json

                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Failed to get rate limit config from cache: {e}")

        # Cache miss - fetch from database
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
                    # Cache the absence of config (negative caching)
                    try:
                        await redis_client.client.setex(
                            cache_key,
                            SourceRateLimiter.CONFIG_CACHE_TTL,
                            "{}",  # Empty dict indicates no limit
                        )
                    except Exception:
                        pass
                    return None

                # Build config dict
                config = {
                    "limit": rate_limit_obj.limit,
                    "window_seconds": rate_limit_obj.window_seconds,
                }

                # Cache for next time
                try:
                    import json

                    await redis_client.client.setex(
                        cache_key,
                        SourceRateLimiter.CONFIG_CACHE_TTL,
                        json.dumps(config),
                    )
                except Exception as e:
                    logger.warning(f"Failed to cache rate limit config: {e}")

                return config

        except Exception as e:
            logger.error(f"Failed to fetch rate limit config from database: {e}")
            return None

    @staticmethod
    async def check_and_increment(
        org_id: UUID,
        source_short_name: str,
        source_connection_id: Optional[UUID] = None,
    ) -> None:
        """Check rate limit and increment counter if allowed.

        Reads rate_limit_level from Source table to determine counting strategy:
        - Connection-level (Notion): Tracks count per user connection
        - Org-level (Google Drive): Tracks count for entire org
        - None: No rate limiting

        The LIMIT is the same for all users/connections (from source_rate_limits table).
        The COUNTS vary based on rate_limit_level (in Redis).

        Args:
            org_id: Organization ID
            source_short_name: Source identifier (e.g., "google_drive", "notion")
            source_connection_id: Source connection ID (used for connection-level sources)

        Raises:
            SourceRateLimitExceededException: If rate limit is exceeded

        Returns:
            None if request is allowed (increments counter)
        """
        # Step 1: Get rate_limit_level from Source table (cached)
        rate_limit_level = await SourceRateLimiter._get_source_rate_limit_level(source_short_name)

        logger.debug(
            f"[SourceRateLimit] Checking source rate limit: org={org_id}, "
            f"source={source_short_name}, connection={source_connection_id}, "
            f"rate_limit_level={rate_limit_level}"
        )

        # Skip if source doesn't use rate limiting
        if not rate_limit_level:
            logger.debug(
                f"[SourceRateLimit] Skipping - source '{source_short_name}' has no rate_limit_level"
            )
            return

        # Step 2: Get limit configuration from DB (ONE row per org+source, cached)
        limit_config = await SourceRateLimiter._get_limit_config(org_id, source_short_name)

        # No limit configured - allow request
        if not limit_config:
            logger.debug(
                f"[SourceRateLimit] Skipping - no limit configured for org={org_id}, "
                f"source={source_short_name}"
            )
            return

        limit = limit_config["limit"]
        window_seconds = limit_config["window_seconds"]

        # Step 3: Build Redis key based on rate_limit_level from Source table
        redis_key = SourceRateLimiter._get_redis_key(
            org_id, source_short_name, rate_limit_level, source_connection_id
        )

        current_time = time.time()
        window_start = current_time - window_seconds
        expire_seconds = window_seconds * 2

        # Generate unique ID for this request (prevents ZADD collision at same timestamp)
        from uuid import uuid4

        unique_id = str(uuid4())

        # Execute atomic Lua script for check-and-increment
        # This prevents race conditions when concurrent requests check simultaneously
        result = await redis_client.client.eval(
            SourceRateLimiter.LUA_CHECK_AND_INCREMENT,
            1,  # Number of keys
            redis_key,  # KEYS[1]
            limit,  # ARGV[1]
            window_start,  # ARGV[2]
            current_time,  # ARGV[3]
            window_seconds,  # ARGV[4]
            expire_seconds,  # ARGV[5]
            unique_id,  # ARGV[6]
        )

        # result = [count, retry_after]
        # If count == -1, we're over the limit
        count_or_error = int(result[0])
        retry_after = float(result[1])

        if count_or_error == -1:
            # Over limit - Lua script calculated retry_after for us
            logger.warning(
                f"Source rate limit exceeded for {source_short_name}. "
                f"{limit}/{limit} requests in {window_seconds}s window, "
                f"retry after {retry_after:.2f}s"
            )

            raise SourceRateLimitExceededException(
                retry_after=retry_after,
                source_short_name=source_short_name,
            )

        # Under limit - request was atomically incremented
        new_count = count_or_error
        logger.debug(
            f"[SourceRateLimit] ✅ Request allowed - {new_count}/{limit} "
            f"requests in window. org={org_id}, source={source_short_name}, "
            f"connection={source_connection_id}, rate_limit_level={rate_limit_level}, "
            f"window={window_seconds}s"
        )

    # Pipedream proxy limits (from Pipedream docs)
    PIPEDREAM_PROXY_LIMIT = 1000
    PIPEDREAM_PROXY_WINDOW = 300  # 5 minutes

    @staticmethod
    async def check_pipedream_proxy_limit(org_id: UUID) -> None:
        """Check Pipedream proxy rate limit (configurable, defaults to 1000 req/5min).

        When using Pipedream's default OAuth (proxy mode), all requests across
        ALL sources/users share this org-wide infrastructure limit.

        Reads limit from source_rate_limits table using special source_short_name='pipedream_proxy'.
        Falls back to hardcoded default (1000 req/5min) if not configured.

        Args:
            org_id: Organization ID

        Raises:
            SourceRateLimitExceededException: If Pipedream proxy limit exceeded
        """
        logger.debug(f"[PipedreamProxy] Checking proxy rate limit for org={org_id}")

        # Get limit from DB using special "pipedream_proxy" source name
        limit_config = await SourceRateLimiter._get_limit_config(org_id, "pipedream_proxy")

        if not limit_config:
            # No custom limit - use hardcoded defaults
            limit = SourceRateLimiter.PIPEDREAM_PROXY_LIMIT  # 1000
            window_seconds = SourceRateLimiter.PIPEDREAM_PROXY_WINDOW  # 300
            logger.debug(
                f"[PipedreamProxy] No custom limit configured, using defaults: "
                f"{limit} req/{window_seconds}s"
            )
        else:
            # Use custom limit from DB
            limit = limit_config["limit"]
            window_seconds = limit_config["window_seconds"]
            logger.debug(
                f"[PipedreamProxy] Using custom limit from DB: {limit} req/{window_seconds}s"
            )

        redis_key = f"pipedream_proxy_rate_limit:{org_id}"

        current_time = time.time()
        window_start = current_time - window_seconds
        expire_seconds = window_seconds * 2

        # Generate unique ID for this request
        from uuid import uuid4

        unique_id = str(uuid4())

        # Execute atomic Lua script for check-and-increment
        result = await redis_client.client.eval(
            SourceRateLimiter.LUA_CHECK_AND_INCREMENT,
            1,  # Number of keys
            redis_key,  # KEYS[1]
            limit,  # ARGV[1]
            window_start,  # ARGV[2]
            current_time,  # ARGV[3]
            window_seconds,  # ARGV[4]
            expire_seconds,  # ARGV[5]
            unique_id,  # ARGV[6]
        )

        # result = [count, retry_after]
        count_or_error = int(result[0])
        retry_after = float(result[1])

        if count_or_error == -1:
            # Over limit
            logger.warning(
                f"Pipedream proxy rate limit exceeded for org {org_id}. "
                f"{limit}/{limit} requests in {window_seconds}s window, "
                f"retry after {retry_after:.2f}s"
            )

            raise SourceRateLimitExceededException(
                retry_after=retry_after, source_short_name="pipedream_proxy"
            )

        # Under limit - request was atomically incremented
        new_count = count_or_error
        logger.debug(
            f"[PipedreamProxy] ✅ Request allowed - {new_count}/{limit} "
            f"requests in window. org={org_id}, window={window_seconds}s"
        )


# Create a global instance
source_rate_limiter = SourceRateLimiter()
