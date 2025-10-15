"""Rate limiter service using Redis for distributed rate limiting."""

import time
from typing import Optional
from uuid import UUID

from airweave.api.context import ApiContext
from airweave.core.exceptions import RateLimitExceededException
from airweave.core.redis_client import redis_client
from airweave.schemas.organization_billing import BillingPlan
from airweave.schemas.rate_limit import RateLimitResult


class RateLimiter:
    """Static rate limiter using Redis for distributed rate limiting.

    Implements distributed rate limiting across horizontally scaled instances
    with plan-based limits that automatically adjust based on billing tier.
    """

    # Plan-based rate limits (requests per minute)
    PLAN_LIMITS = {
        BillingPlan.DEVELOPER: 10,
        BillingPlan.PRO: 100,
        BillingPlan.TEAM: 250,
        BillingPlan.ENTERPRISE: None,  # Unlimited
    }

    WINDOW_SIZE = 60  # 1 minute window for per-minute rate limiting

    # Redis key prefix
    KEY_PREFIX = "rate_limit:org"

    @staticmethod
    async def _get_rate_limit(
        ctx: ApiContext,
    ) -> Optional[int]:
        """Get the rate limit for the organization based on billing plan.

        Uses cached billing data from ctx.organization (loaded via deps.py)
        to avoid additional database queries.

        Args:
            ctx: The API context with enriched organization data

        Returns:
            Rate limit (requests per minute) or None for unlimited
        """
        # Check if organization has billing info (from cache/DB in deps.py)
        if not ctx.organization.billing or not ctx.organization.billing.current_period:
            # Legacy organizations or those without billing get Pro tier limits
            ctx.logger.debug(
                f"Organization {ctx.organization.id} has no billing/period - using Pro tier limits"
            )
            return RateLimiter.PLAN_LIMITS[BillingPlan.PRO]

        # Get plan from cached current period
        current_period = ctx.organization.billing.current_period

        if not current_period.plan:
            # Default to Developer limits if no plan found
            plan = BillingPlan.DEVELOPER
        else:
            try:
                plan = (
                    current_period.plan
                    if hasattr(current_period.plan, "value")
                    else BillingPlan(str(current_period.plan))
                )
            except Exception:
                plan = BillingPlan.DEVELOPER

        rate_limit = RateLimiter.PLAN_LIMITS.get(
            plan, RateLimiter.PLAN_LIMITS[BillingPlan.DEVELOPER]
        )

        ctx.logger.debug(
            f"Rate limit for organization {ctx.organization.id}: "
            f"{rate_limit} req/min (plan: {plan.value if hasattr(plan, 'value') else plan})"
        )

        return rate_limit

    @staticmethod
    def _get_redis_key(organization_id: UUID) -> str:
        """Get the Redis key for this organization's rate limit.

        Args:
            organization_id: The organization ID

        Returns:
            Redis key string
        """
        return f"{RateLimiter.KEY_PREFIX}:{organization_id}"

    @staticmethod
    async def check_rate_limit(
        ctx: ApiContext,
    ) -> RateLimitResult:
        """Check if the request should be allowed based on rate limit.

        Uses Redis ZSET with sliding window algorithm for accurate rate limiting
        across distributed instances.

        Args:
            ctx: The API context

        Returns:
            RateLimitResult containing:
                - allowed: Whether the request should be allowed
                - retry_after: Seconds until rate limit resets (0.0 if allowed)
                - limit: Maximum requests per window (0 indicates unlimited)
                - remaining: Requests remaining in current window

        Raises:
            RateLimitExceededException: If rate limit is exceeded
        """
        # Get rate limit for this organization
        rate_limit = await RateLimiter._get_rate_limit(ctx)

        # No limit means unlimited
        if rate_limit is None:
            ctx.logger.debug(f"Organization {ctx.organization.id} has unlimited rate limit")
            return RateLimitResult(
                allowed=True,
                retry_after=0.0,
                limit=0,
                remaining=0,
            )

        current_time = time.time()
        window_start = current_time - RateLimiter.WINDOW_SIZE
        redis_key = RateLimiter._get_redis_key(ctx.organization.id)

        # Use Redis pipeline for atomic operations
        pipe = redis_client.client.pipeline()

        # Remove old entries outside the sliding window
        pipe.zremrangebyscore(redis_key, 0, window_start)

        # Count current requests in window
        pipe.zcount(redis_key, window_start, current_time)

        # Execute pipeline
        results = await pipe.execute()
        current_count = results[1]  # Result from zcount

        # Calculate remaining requests
        remaining = max(0, rate_limit - current_count)

        # Check if we're over the limit
        if current_count >= rate_limit:
            # Calculate when the oldest request will expire
            oldest_entries = await redis_client.client.zrange(redis_key, 0, 0, withscores=True)

            if oldest_entries:
                oldest_timestamp = float(oldest_entries[0][1])
                retry_after = max(0.1, (oldest_timestamp + RateLimiter.WINDOW_SIZE) - current_time)
            else:
                retry_after = RateLimiter.WINDOW_SIZE

            ctx.logger.warning(
                f"Rate limit exceeded. {current_count}/{rate_limit} requests in window, "
                f"retry after {retry_after:.2f}s"
            )

            raise RateLimitExceededException(
                retry_after=retry_after,
                limit=rate_limit,
                remaining=0,
            )

        # Add current request to the sliding window
        await redis_client.client.zadd(redis_key, {str(current_time): current_time})

        # Set expiration on the key to auto-cleanup
        await redis_client.client.expire(redis_key, RateLimiter.WINDOW_SIZE * 2)

        ctx.logger.debug(
            f"Rate limit check passed. {current_count + 1}/{rate_limit} requests in window, "
            f"{remaining - 1} remaining"
        )

        return RateLimitResult(
            allowed=True,
            retry_after=0.0,
            limit=rate_limit,
            remaining=remaining - 1,
        )
