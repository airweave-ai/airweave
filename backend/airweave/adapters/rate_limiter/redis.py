"""Redis-backed rate limiter using sliding window (sorted sets).

The adapter reads billing plan info directly from the enriched Organization
schema. Missing billing data is a data integrity error, not a fallback case.
"""

import logging
import time
from typing import Any, Optional

from airweave import schemas
from airweave.core.exceptions import RateLimitExceededException
from airweave.core.protocols.rate_limiter import RateLimiter
from airweave.schemas.organization_billing import BillingPlan
from airweave.schemas.rate_limit import RateLimitResult

logger = logging.getLogger(__name__)

PLAN_LIMITS: dict[str, Optional[int]] = {
    BillingPlan.DEVELOPER.value: 10,
    BillingPlan.TRIAL.value: 10,
    BillingPlan.PRO.value: 100,
    BillingPlan.TEAM.value: 250,
    BillingPlan.ENTERPRISE.value: None,
}

WINDOW_SIZE = 60  # seconds
KEY_PREFIX = "rate_limit:org"
UNLIMITED = RateLimitResult(allowed=True, retry_after=0.0, limit=9999, remaining=9999)


class RedisRateLimiter(RateLimiter):
    """Sliding-window rate limiter backed by Redis sorted sets."""

    def __init__(self, redis_client: Any) -> None:
        """Initialize with an async Redis client."""
        self._redis = redis_client

    async def check(self, organization: schemas.Organization) -> RateLimitResult:
        """Check and record a request against the sliding window."""
        plan_str = self._extract_plan(organization)
        limit = PLAN_LIMITS.get(plan_str, PLAN_LIMITS[BillingPlan.DEVELOPER.value])
        if limit is None:
            return UNLIMITED

        now = time.time()
        window_start = now - WINDOW_SIZE
        key = f"{KEY_PREFIX}:{organization.id}"

        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcount(key, window_start, now)
        results = await pipe.execute()
        current_count = results[1]

        remaining = max(0, limit - current_count)

        if current_count >= limit:
            oldest = await self._redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                retry_after = max(0.1, (float(oldest[0][1]) + WINDOW_SIZE) - now)
            else:
                retry_after = float(WINDOW_SIZE)

            raise RateLimitExceededException(
                retry_after=retry_after,
                limit=limit,
                remaining=0,
            )

        await self._redis.zadd(key, {str(now): now})
        await self._redis.expire(key, WINDOW_SIZE * 2)

        return RateLimitResult(
            allowed=True,
            retry_after=0.0,
            limit=limit,
            remaining=remaining - 1,
        )

    @staticmethod
    def _extract_plan(organization: schemas.Organization) -> str:
        """Read the billing plan from the enriched Organization schema.

        Raises RuntimeError if billing data is missing — that is a data
        integrity problem in the enrichment pipeline, not something to
        silently fall back from.
        """
        if not organization.billing:
            raise RuntimeError(
                f"Organization {organization.id} has no billing record. "
                f"Rate limiting requires an active billing record."
            )
        if not organization.billing.current_period:
            raise RuntimeError(
                f"Organization {organization.id} has no active billing period. "
                f"Rate limiting requires a current billing period."
            )
        return organization.billing.current_period.plan.value
