"""Rate limiter service using Redis for distributed rate limiting."""

import time
from typing import Optional, Tuple
from uuid import UUID

from airweave import crud
from airweave.core.config import settings
from airweave.core.exceptions import RateLimitExceededException
from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.core.redis_client import redis_client
from airweave.db.session import get_db_context
from airweave.schemas.organization_billing import BillingPlan


class RateLimiterService:
    """Redis-backed rate limiter using sliding window algorithm.

    Implements distributed rate limiting across horizontally scaled instances
    with plan-based limits that automatically adjust based on billing tier.
    """

    # Plan-based rate limits (requests per second)
    PLAN_LIMITS = {
        BillingPlan.DEVELOPER: 10,
        BillingPlan.PRO: 25,
        BillingPlan.TEAM: 50,
        BillingPlan.ENTERPRISE: None,  # Unlimited
    }

    # Sliding window duration in seconds
    WINDOW_SIZE = 1  # 1 second window for per-second rate limiting

    # Redis key prefix
    KEY_PREFIX = "rate_limit:org"

    def __init__(self, organization_id: UUID, logger: Optional[ContextualLogger] = None):
        """Initialize the rate limiter service.

        Args:
            organization_id: The organization ID to rate limit
            logger: Optional contextual logger for structured logging
        """
        self.organization_id = organization_id
        self.logger = logger or default_logger.with_context(component="rate_limiter")
        self._cached_limit: Optional[int] = None
        self._has_billing: Optional[bool] = None

    async def _check_has_billing(self) -> bool:
        """Check if the organization has billing enabled.

        Returns:
            True if organization has billing records, False for legacy organizations
        """
        if self._has_billing is not None:
            return self._has_billing

        async with get_db_context() as db:
            billing_record = await crud.organization_billing.get_by_organization(
                db, organization_id=self.organization_id
            )
            self._has_billing = billing_record is not None

            if not self._has_billing:
                self.logger.debug(
                    f"Organization {self.organization_id} is a legacy organization without billing"
                )

        return self._has_billing

    async def _get_rate_limit(self) -> Optional[int]:
        """Get the rate limit for the organization based on billing plan.

        Returns:
            Rate limit (requests per second) or None for unlimited
        """
        if self._cached_limit is not None:
            return self._cached_limit

        # Check if organization has billing
        has_billing = await self._check_has_billing()
        if not has_billing:
            # Legacy organizations get Pro tier limits
            self._cached_limit = self.PLAN_LIMITS[BillingPlan.PRO]
            return self._cached_limit

        async with get_db_context() as db:
            # Get current billing period to determine plan
            current_period = await crud.billing_period.get_current_period(
                db, organization_id=self.organization_id
            )

            if not current_period or not current_period.plan:
                # Default to Developer limits if no period found
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

            self._cached_limit = self.PLAN_LIMITS.get(plan, self.PLAN_LIMITS[BillingPlan.DEVELOPER])

            self.logger.debug(
                f"Rate limit for organization {self.organization_id}: "
                f"{self._cached_limit} req/s (plan: {plan.value if hasattr(plan, 'value') else plan})"
            )

            return self._cached_limit

    def _get_redis_key(self) -> str:
        """Get the Redis key for this organization's rate limit.

        Returns:
            Redis key string
        """
        return f"{self.KEY_PREFIX}:{self.organization_id}"

    async def check_rate_limit(self) -> Tuple[bool, float, int, int]:
        """Check if the request should be allowed based on rate limit.

        Uses Redis ZSET with sliding window algorithm for accurate rate limiting
        across distributed instances.

        Returns:
            Tuple of (allowed, retry_after, limit, remaining):
                - allowed: Whether the request should be allowed
                - retry_after: Seconds until rate limit resets (0 if allowed)
                - limit: Maximum requests per window
                - remaining: Requests remaining in current window

        Raises:
            RateLimitExceededException: If rate limit is exceeded
        """
        # Bypass rate limiting in local development
        if settings.LOCAL_DEVELOPMENT or not settings.RATE_LIMIT_ENABLED:
            return True, 0.0, 9999, 9999

        # Get rate limit for this organization
        rate_limit = await self._get_rate_limit()

        # No limit means unlimited
        if rate_limit is None:
            self.logger.debug(f"Organization {self.organization_id} has unlimited rate limit")
            return True, 0.0, 0, 0

        current_time = time.time()
        window_start = current_time - self.WINDOW_SIZE
        redis_key = self._get_redis_key()

        try:
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
                    retry_after = max(0.1, (oldest_timestamp + self.WINDOW_SIZE) - current_time)
                else:
                    retry_after = self.WINDOW_SIZE

                self.logger.warning(
                    f"Rate limit exceeded for organization {self.organization_id}: "
                    f"{current_count}/{rate_limit} requests in window, "
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
            await redis_client.client.expire(redis_key, self.WINDOW_SIZE * 2)

            self.logger.debug(
                f"Rate limit check passed for organization {self.organization_id}: "
                f"{current_count + 1}/{rate_limit} requests in window, "
                f"{remaining - 1} remaining"
            )

            return True, 0.0, rate_limit, remaining - 1

        except RateLimitExceededException:
            # Re-raise rate limit exceptions
            raise
        except Exception as e:
            # Log error but allow request through on Redis failures
            self.logger.error(
                f"Redis error during rate limit check: {e}. Allowing request.",
                exc_info=True,
            )
            return True, 0.0, rate_limit or 0, 0
