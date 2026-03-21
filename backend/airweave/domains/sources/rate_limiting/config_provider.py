"""Concrete rate limit config provider backed by DB + Redis cache."""

from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

import redis.asyncio as aioredis

from airweave.core.logging import logger
from airweave.crud.crud_source_rate_limit import source_rate_limit as rate_limit_crud
from airweave.db.session import get_db_context
from airweave.domains.sources.rate_limiting.protocols import RateLimitConfigProvider
from airweave.domains.sources.rate_limiting.types import RateLimitConfig

_CACHE_PREFIX = "source_rate_limit_config"
_CACHE_TTL = 300
_NEGATIVE_CACHE = object()


class DatabaseRateLimitConfigProvider(RateLimitConfigProvider):
    """Fetches rate limit config from the DB, caches in Redis for 5 minutes.

    Negative results (no limit configured) are also cached to avoid
    repeated DB round-trips.
    """

    def __init__(self, redis: aioredis.Redis) -> None:
        """Initialize with an async Redis client for caching."""
        self._redis = redis

    async def get_config(self, org_id: UUID, source_short_name: str) -> Optional[RateLimitConfig]:
        """Get rate limit config, checking Redis cache first."""
        cache_key = f"{_CACHE_PREFIX}:{org_id}:{source_short_name}"

        cached = await self._read_cache(cache_key)
        if cached is _NEGATIVE_CACHE:
            return None
        if cached is not None:
            return cached

        config = await self._fetch_from_db(org_id, source_short_name)
        await self._write_cache(cache_key, config)
        return config

    async def _read_cache(self, cache_key: str) -> Optional[RateLimitConfig | object]:
        """Read from Redis. Returns config, _NEGATIVE_CACHE sentinel, or None (miss)."""
        try:
            raw = await self._redis.get(cache_key)
            if raw is None:
                return None
            parsed = json.loads(raw)
            if not parsed:
                return _NEGATIVE_CACHE
            return RateLimitConfig(limit=parsed["limit"], window_seconds=parsed["window_seconds"])
        except Exception:
            return None

    async def _write_cache(self, cache_key: str, config: Optional[RateLimitConfig]) -> None:
        """Write to Redis. Empty dict signals 'no limit configured'."""
        try:
            if config:
                value = json.dumps({"limit": config.limit, "window_seconds": config.window_seconds})
            else:
                value = "{}"
            await self._redis.setex(cache_key, _CACHE_TTL, value)
        except Exception as e:
            logger.warning(f"Failed to cache rate limit config: {e}")

    @staticmethod
    async def _fetch_from_db(org_id: UUID, source_short_name: str) -> Optional[RateLimitConfig]:
        """Query the DB for rate limit configuration."""
        try:
            async with get_db_context() as db:
                obj = await rate_limit_crud.get_limit(
                    db, org_id=org_id, source_short_name=source_short_name
                )
                if not obj:
                    return None
                return RateLimitConfig(limit=obj.limit, window_seconds=obj.window_seconds)
        except Exception as e:
            logger.error(f"Failed to fetch rate limit config from DB: {e}")
            return None
