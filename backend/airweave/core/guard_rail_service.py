"""Guard rail service."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select

from airweave import crud
from airweave.core.config import settings
from airweave.core.exceptions import PaymentRequiredException, UsageLimitExceededException
from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.core.shared_models import ActionType
from airweave.db.session import get_db_context
from airweave.models.user_organization import UserOrganization
from airweave.schemas.billing_period import BillingPeriodStatus
from airweave.schemas.organization_billing import BillingPlan
from airweave.schemas.usage import Usage, UsageLimit

# NOTE: usage is always got from the database and we never directly update the usage in memory


class GuardRailService:
    """Guard rail service."""

    # Per-action-type flush thresholds
    FLUSH_THRESHOLDS = {
        ActionType.ENTITIES: 100,
        ActionType.QUERIES: 1,
        ActionType.SOURCE_CONNECTIONS: 1,
    }

    # Cache TTL - refresh usage data after this duration
    USAGE_CACHE_TTL = timedelta(seconds=30)  # Refresh every 30 seconds

    # Billing status restrictions - which actions are blocked for each billing status
    BILLING_STATUS_RESTRICTIONS = {
        BillingPeriodStatus.ACTIVE: set(),  # No restrictions
        BillingPeriodStatus.TRIAL: set(),  # No restrictions during trial
        BillingPeriodStatus.GRACE: {
            # During grace period, block resource creation but allow queries
            ActionType.SOURCE_CONNECTIONS,
        },
        BillingPeriodStatus.ENDED_UNPAID: {
            # When unpaid, only allow queries - block all resource creation/modification
            ActionType.ENTITIES,
            ActionType.SOURCE_CONNECTIONS,
        },
        BillingPeriodStatus.COMPLETED: {
            # Completed periods should not be current, but if they are, block everything
            ActionType.ENTITIES,
            ActionType.SOURCE_CONNECTIONS,
            ActionType.QUERIES,
        },
    }

    # Plan limits configuration (matching BillingService)
    PLAN_LIMITS = {
        BillingPlan.DEVELOPER: {
            "max_entities": 50000,
            "max_queries": 500,
            "max_source_connections": 10,
            "max_team_members": 1,
        },
        BillingPlan.PRO: {
            "max_entities": 100000,
            "max_queries": 2000,
            "max_source_connections": 50,
            "max_team_members": 2,
        },
        BillingPlan.TEAM: {
            "max_entities": 1000000,
            "max_queries": 10000,
            "max_source_connections": 1000,
            "max_team_members": 10,
        },
        BillingPlan.ENTERPRISE: {
            "max_entities": None,
            "max_queries": None,
            "max_source_connections": None,
            "max_team_members": None,
        },
    }

    def __init__(self, organization_id: UUID, logger: Optional[ContextualLogger] = None):
        """Initialize the guard rail service.

        Args:
            organization_id: The organization ID to get usage for
            logger: Optional contextual logger for structured logging
        """
        self.organization_id = organization_id
        self.logger = logger or default_logger.with_context(component="guardrail")
        self.logger.debug(f"Initialized GuardRailService for organization {organization_id}")
        self.usage: Optional[Usage] = None
        self.usage_limit: Optional[UsageLimit] = None
        self.usage_fetched_at: Optional[datetime] = None
        self._has_billing: Optional[bool] = None  # Cache whether org has billing
        # Track pending increments in memory (team_members not included - it's counted dynamically)
        self.pending_increments = {
            ActionType.ENTITIES: 0,
            ActionType.QUERIES: 0,
            ActionType.SOURCE_CONNECTIONS: 0,
        }
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def _check_has_billing(self) -> bool:
        """Check if the organization has billing records.

        This is a pure check that only determines if billing exists,
        without considering environment or enforcement policy.

        Returns:
            True if organization has billing records, False otherwise
        """
        if self._has_billing is not None:
            return self._has_billing

        # If Stripe is disabled, no organizations have billing
        if not settings.STRIPE_ENABLED:
            self._has_billing = False
            return self._has_billing

        async with get_db_context() as db:
            # Check if organization has billing record
            billing_record = await crud.organization_billing.get_by_organization(
                db, organization_id=self.organization_id
            )
            self._has_billing = billing_record is not None

        return self._has_billing

    def _should_enforce_usage_limits(self) -> bool:
        """Determine if usage limits should be enforced.

        Returns:
            False if local development mode, True otherwise
        """
        if settings.LOCAL_DEVELOPMENT:
            self.logger.debug("Local development mode - usage limits disabled")
            return False
        return True

    async def is_allowed(self, action_type: ActionType, amount: int = 1) -> bool:
        """Check if the action is allowed.

        Args:
            action_type: The type of action to check
            amount: Number of units to check (default 1)

        Returns:
            True if the action is allowed

        Raises:
            PaymentRequiredException: If action is blocked due to billing status
            UsageLimitExceededException: If action would exceed usage limits
        """
        # Use lock to ensure thread-safe access to usage data
        async with self._lock:
            # Check if we should enforce limits (local dev bypass)
            if not self._should_enforce_usage_limits():
                return True

            # Check if organization has billing - legacy orgs are exempt
            has_billing = await self._check_has_billing()
            if not has_billing:
                self.logger.debug(
                    f"No billing for organization {self.organization_id} - allowing action"
                )
                return True

            # First check billing status
            billing_status = await self._get_billing_status()
            restricted_actions = self.BILLING_STATUS_RESTRICTIONS.get(billing_status, set())

            # If action is restricted due to billing status, raise exception
            if action_type in restricted_actions:
                self.logger.warning(
                    f"Action {action_type.value} blocked due to "
                    f"billing status: {billing_status.value}"
                )
                raise PaymentRequiredException(
                    action_type=action_type.value,
                    payment_status=billing_status.value,
                )

            # Special handling for team members - count from UserOrganization table
            if action_type == ActionType.TEAM_MEMBERS:
                return await self._check_team_members_allowed(amount)

            # Check if we need to refresh usage (TTL expired or never fetched)
            should_refresh = (
                self.usage is None
                or self.usage_fetched_at is None
                or datetime.utcnow() - self.usage_fetched_at > self.USAGE_CACHE_TTL
            )

            if should_refresh:
                self.usage = await self._get_usage()
                self.usage_fetched_at = datetime.utcnow()

            # Lazy load usage limit if not already loaded
            if self.usage_limit is None:
                self.usage_limit = await self._infer_usage_limit()

            # Get current value from usage plus pending increments
            current_value = getattr(self.usage, action_type.value, 0) if self.usage else 0
            pending = self.pending_increments.get(action_type, 0)
            total_usage = current_value + pending

            # Get the limit for this action type
            # Map action type to the corresponding max_ field in UsageLimit
            limit_field = f"max_{action_type.value}"
            limit = getattr(self.usage_limit, limit_field, None) if self.usage_limit else None

            # If no limit (None), it's unlimited - always allowed
            if limit is None:
                self.logger.debug(f"Action {action_type.value} has unlimited usage")
                return True

            # Check if we have enough quota for the requested amount
            if total_usage + amount > limit:
                self.logger.warning(
                    f"Usage limit exceeded for {action_type.value}: "
                    f"current={total_usage}, requested={amount}, limit={limit}"
                )
                raise UsageLimitExceededException(
                    action_type=action_type.value,
                    limit=limit,
                    current_usage=total_usage,
                )

            self.logger.info(
                f"\n\nUsage check: {action_type.value} usage={total_usage}, "
                f"requested={amount}, limit={limit}\n\n"
            )

            return True

    async def increment(self, action_type: ActionType, amount: int = 1) -> None:
        """Increment the usage for the action.

        Args:
            action_type: The type of action to increment
            amount: The amount to increment by (default 1)
        """
        # Team members are not tracked as cumulative usage - they're counted dynamically
        if action_type == ActionType.TEAM_MEMBERS:
            self.logger.debug(
                "Team members are tracked dynamically, not incrementing usage counter"
            )
            return

        # Use lock to ensure thread-safe increment and flush
        async with self._lock:
            # Check if we should track usage
            if not self._should_enforce_usage_limits():
                return

            # Skip incrementing if no billing records exist
            has_billing = await self._check_has_billing()
            if not has_billing:
                self.logger.debug(
                    f"No billing for organization {self.organization_id} - skipping usage tracking"
                )
                return

            # Add to pending increments
            self.pending_increments[action_type] = (
                self.pending_increments.get(action_type, 0) + amount
            )

            # Check if this specific action type should flush
            threshold = self.FLUSH_THRESHOLDS.get(action_type, 1)
            if self.pending_increments[action_type] >= threshold:
                await self._flush_usage_internal(action_type)

    async def decrement(self, action_type: ActionType, amount: int = 1) -> None:
        """Decrement the usage for the action."""
        # Team members are not tracked as cumulative usage
        if action_type == ActionType.TEAM_MEMBERS:
            self.logger.debug(
                "Team members are tracked dynamically, not decrementing usage counter"
            )
            return

        async with self._lock:
            self.pending_increments[action_type] = (
                self.pending_increments.get(action_type, 0) - amount
            )
            self.logger.debug(
                f"Decremented {action_type.value} by {amount}, "
                f"pending total: {self.pending_increments[action_type]}"
            )

            # Check if this specific action type should flush
            threshold = self.FLUSH_THRESHOLDS.get(action_type, 1)
            if self.pending_increments[action_type] >= threshold:
                await self._flush_usage_internal(action_type)

    async def _flush_usage_internal(self, action_type: Optional[ActionType] = None) -> None:
        """Flush pending increments to the database using atomic operations.

        This is the internal method that should only be called while holding the lock.

        Args:
            action_type: If specified, only flush this action type. Otherwise flush all.
        """
        # Check if we should track usage
        if not self._should_enforce_usage_limits():
            return

        # Skip flushing if no billing records exist
        has_billing = await self._check_has_billing()
        if not has_billing:
            self.logger.debug(
                f"No billing for organization {self.organization_id} - skipping usage flush"
            )
            return

        self.logger.info(f"Flushing usage to database for {action_type or 'all action types'}")

        # Determine what to flush
        if action_type is not None:
            # Flush specific action type if it has pending increments
            if self.pending_increments.get(action_type, 0) == 0:
                return
            increments_to_flush = {action_type: self.pending_increments[action_type]}
        else:
            # Flush all non-zero increments
            increments_to_flush = {
                action_type: count
                for action_type, count in self.pending_increments.items()
                if count > 0
            }

        # Perform database operations outside the lock
        self.logger.info(f"Persisting usage increments to database: {increments_to_flush}")
        if increments_to_flush:
            async with get_db_context() as db:
                # Capture the updated usage record returned from increment_usage
                updated_usage_record = await crud.usage.increment_usage(
                    db, organization_id=self.organization_id, increments=increments_to_flush
                )

                # Update in-memory usage with the fresh database values
                if updated_usage_record:
                    self.usage = Usage.model_validate(updated_usage_record)
                    # Populate team_members field (not stored in database)
                    self.usage.team_members = await self._count_team_members()
                    self.usage_fetched_at = datetime.utcnow()
                    self.logger.info(
                        f"Updated in-memory usage from database: "
                        f"entities={self.usage.entities}, queries={self.usage.queries}, "
                        f"source_connections={self.usage.source_connections}, "
                        f"team_members={self.usage.team_members}"
                    )

                # Clear flushed increments
                for action_type in increments_to_flush:
                    self.pending_increments[action_type] = 0

    async def _flush_usage(self, action_type: Optional[ActionType] = None) -> None:
        """Public flush method that acquires the lock before flushing.

        Args:
            action_type: If specified, only flush this action type. Otherwise flush all.
        """
        async with self._lock:
            await self._flush_usage_internal(action_type)

    async def flush_all(self) -> None:
        """Flush all pending increments to the database.

        This method should be called when a sync is about to terminate
        (either successfully or due to failure) to ensure no usage data is lost.
        """
        self.logger.info("Flushing all pending usage increments before termination")
        try:
            # Use the public flush method which handles locking
            await self._flush_usage(action_type=None)
            self.logger.info("Successfully flushed all pending usage increments")
        except Exception as e:
            self.logger.error(f"Failed to flush usage increments: {str(e)}", exc_info=True)
            # Re-raise to ensure caller knows flush failed
            raise

    async def _get_usage(self) -> Optional[Usage]:
        """Get usage from the database using crud_usage.

        Returns:
            The current usage record for the organization's active billing period,
            or None if not found.
        """
        self.logger.debug(
            f"Fetching current usage from database for organization {self.organization_id}"
        )
        async with get_db_context() as db:
            # Get usage for current billing period
            usage_record = await crud.usage.get_current_usage(
                db, organization_id=self.organization_id
            )
            if usage_record:
                # Convert SQLAlchemy model to Pydantic schema
                usage = Usage.model_validate(usage_record)
                # Populate team_members field (not stored in database)
                usage.team_members = await self._count_team_members()
                self.logger.info(
                    f"\n\nRetrieved current usage: entities={usage.entities}, "
                    f"queries={usage.queries}, "
                    f"source_connections={usage.source_connections}, "
                    f"team_members={usage.team_members}\n\n"
                )
                return usage
            else:
                self.logger.info("No usage record found for current billing period")
                return None

    async def _get_billing_status(self) -> BillingPeriodStatus:
        """Get billing status from the current billing period.

        Returns:
            BillingPeriodStatus based on the current billing period

        Note:
            This method assumes billing exists - should only be called after checking _has_billing
        """
        async with get_db_context() as db:
            # Get current billing period
            current_period = await crud.billing_period.get_current_period(
                db, organization_id=self.organization_id
            )

            if not current_period:
                # For organizations with billing but no active period, default to ACTIVE
                # This can happen during transitions or initial setup
                self.logger.warning(
                    f"Organization {self.organization_id} has billing but no active period. "
                    "Defaulting to ACTIVE status."
                )
                return BillingPeriodStatus.ACTIVE

            if not current_period.status:
                # This should not happen, but handle gracefully
                self.logger.error(
                    f"Billing period {current_period.id} has no status. "
                    "Defaulting to ACTIVE status."
                )
                return BillingPeriodStatus.ACTIVE

            self.logger.info(
                f"\n\nRetrieved billing period for organization {self.organization_id}: "
                f"status={current_period.status}, plan={current_period.plan}, "
                f"period_id={current_period.id}, "
                f"period={current_period.period_start} to {current_period.period_end}\n\n"
            )

            return current_period.status

    async def _get_current_plan(self) -> BillingPlan:
        """Get the organization's current billing plan.

        Falls back to developer if no active period is found.
        """
        async with get_db_context() as db:
            current_period = await crud.billing_period.get_current_period(
                db, organization_id=self.organization_id
            )
            if not current_period or not current_period.plan:
                return BillingPlan.DEVELOPER
            return current_period.plan

    async def get_team_member_count(self) -> int:
        """Get the current number of team members in the organization.

        Public method for retrieving team member count for usage reporting.

        Returns:
            Current number of team members
        """
        return await self._count_team_members()

    async def _count_team_members(self) -> int:
        """Count current team members in the organization."""
        async with get_db_context() as db:
            stmt = (
                select(func.count())
                .select_from(UserOrganization)
                .where(UserOrganization.organization_id == self.organization_id)
            )
            result = await db.execute(stmt)
            return int(result.scalar_one() or 0)

    async def _check_team_members_allowed(self, amount: int) -> bool:
        """Check if adding team members is allowed.

        Args:
            amount: Number of team members to add

        Returns:
            True if allowed

        Raises:
            UsageLimitExceededException: If limit would be exceeded
        """
        current_count = await self._count_team_members()

        # Get limit from usage limit or plan limits
        if self.usage_limit is None:
            self.usage_limit = await self._infer_usage_limit()

        max_team_members = getattr(self.usage_limit, "max_team_members", None)

        # If no limit (None), it's unlimited - always allowed
        if max_team_members is None:
            self.logger.debug("Team members have unlimited usage")
            return True

        # Check if adding the requested amount would exceed the limit
        if current_count + amount > max_team_members:
            self.logger.warning(
                f"Team member limit exceeded: current={current_count}, "
                f"requested={amount}, limit={max_team_members}"
            )
            raise UsageLimitExceededException(
                action_type="team_members",
                limit=max_team_members,
                current_usage=current_count,
            )

        self.logger.info(
            f"Team member check: current={current_count}, "
            f"requested={amount}, limit={max_team_members}"
        )
        return True

    async def _infer_usage_limit(self) -> UsageLimit:
        """Infer usage limit based on current billing period's plan.

        Returns:
            UsageLimit based on organization's subscription tier

        Note:
            This method assumes billing exists - should only be called after checking _has_billing
        """
        async with get_db_context() as db:
            # Get current billing period
            current_period = await crud.billing_period.get_current_period(
                db, organization_id=self.organization_id
            )

        if not current_period or not current_period.plan:
            # Default to developer limits if no period found
            self.logger.warning(
                f"No active billing period found for organization {self.organization_id}. "
                "Using developer plan limits as default."
            )
            plan = BillingPlan.DEVELOPER
        else:
            # Normalize plan to enum if needed
            try:
                plan = (
                    current_period.plan
                    if hasattr(current_period, "plan") and hasattr(current_period.plan, "value")
                    else BillingPlan(str(current_period.plan))
                )
            except Exception:
                plan = BillingPlan.DEVELOPER
            self.logger.info(
                f"\n\nRetrieved billing period for limits calculation: "
                f"plan={plan}, status={current_period.status}, "
                f"period_id={current_period.id}, "
                f"organization_id={self.organization_id}\n\n"
            )

        # Get limits for the plan
        limits = self.PLAN_LIMITS.get(plan, self.PLAN_LIMITS[BillingPlan.DEVELOPER])

        self.logger.debug(
            f"Applied limits for {plan} plan: "
            f"entities={limits.get('max_entities')}, "
            f"queries={limits.get('max_queries')}, "
            f"source_connections={limits.get('max_source_connections')}"
        )

        return UsageLimit(
            max_entities=limits.get("max_entities"),
            max_queries=limits.get("max_queries"),
            max_source_connections=limits.get("max_source_connections"),
            max_team_members=limits.get("max_team_members"),
        )
