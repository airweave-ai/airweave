"""Usage enforcement service.

Refactored from core/guard_rail_service.py. Tracks per-organization usage,
enforces plan limits, and batches database writes for performance.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.logging import ContextualLogger
from airweave.domains.billing.repository import (
    BillingPeriodRepositoryProtocol,
    OrganizationBillingRepositoryProtocol,
)
from airweave.domains.organizations.protocols import UserOrganizationRepositoryProtocol
from airweave.domains.source_connections.protocols import SourceConnectionRepositoryProtocol
from airweave.domains.usage.exceptions import PaymentRequiredError, UsageLimitExceededError
from airweave.domains.usage.protocols import UsageGuardrailProtocol
from airweave.domains.usage.repository import UsageRepositoryProtocol
from airweave.domains.usage.types import (
    BILLING_STATUS_RESTRICTIONS,
    ActionType,
    infer_usage_limit,
)
from airweave.schemas.billing_period import BillingPeriodStatus
from airweave.schemas.organization_billing import BillingPlan
from airweave.schemas.usage import Usage, UsageLimit

# Per-action-type flush thresholds: how many pending increments
# before we flush to the database.
_FLUSH_THRESHOLDS: dict[ActionType, int] = {
    ActionType.ENTITIES: 100,
    ActionType.QUERIES: 1,
}

# Cache TTL — refresh usage data from the database after this duration.
_USAGE_CACHE_TTL = timedelta(seconds=30)



class UsageGuardrailService(UsageGuardrailProtocol):
    """Per-organization usage tracking and limit enforcement.

    Stateful: caches usage data, buffers increments, and uses an asyncio.Lock
    for thread safety.  Created via UsageServiceFactory.create().
    """

    def __init__(
        self,
        organization_id: UUID,
        usage_repo: UsageRepositoryProtocol,
        billing_repo: OrganizationBillingRepositoryProtocol,
        period_repo: BillingPeriodRepositoryProtocol,
        sc_repo: SourceConnectionRepositoryProtocol,
        user_org_repo: UserOrganizationRepositoryProtocol,
        logger: ContextualLogger,
    ) -> None:
        """Initialize with repository dependencies and organization context."""
        self.organization_id = organization_id
        self.logger = logger

        self._usage_repo = usage_repo
        self._billing_repo = billing_repo
        self._period_repo = period_repo
        self._sc_repo = sc_repo
        self._user_org_repo = user_org_repo

        # Cached state
        self.usage: Optional[Usage] = None
        self.usage_limit: Optional[UsageLimit] = None
        self.usage_fetched_at: Optional[datetime] = None
        self._has_billing: Optional[bool] = None
        self.pending_increments: dict[ActionType, int] = {
            ActionType.ENTITIES: 0,
            ActionType.QUERIES: 0,
        }
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def is_allowed(self, db: AsyncSession, action_type: ActionType, amount: int = 1) -> bool:
        """Check if *amount* units of *action_type* are allowed.

        Returns True when allowed.  Raises UsageLimitExceededError or
        PaymentRequiredError when not.
        """
        async with self._lock:
            has_billing = await self._check_has_billing(db)
            if not has_billing:
                self.logger.debug(
                    f"No billing for organization {self.organization_id} - allowing action"
                )
                return True

            # Check billing-status restrictions first
            billing_status = await self._get_billing_status(db)
            restricted = BILLING_STATUS_RESTRICTIONS.get(billing_status, set())
            if action_type in restricted:
                self.logger.warning(
                    f"Action {action_type.value} blocked due to "
                    f"billing status: {billing_status.value}"
                )
                raise PaymentRequiredError(
                    action_type=action_type.value,
                    payment_status=billing_status.value,
                )

            # Dynamic metrics — counted live from DB
            if action_type == ActionType.TEAM_MEMBERS:
                return await self._check_dynamic_metric_allowed(
                    db,
                    action_type,
                    amount,
                    self._user_org_repo.count_members,
                    "max_team_members",
                )
            if action_type == ActionType.SOURCE_CONNECTIONS:
                return await self._check_dynamic_metric_allowed(
                    db,
                    action_type,
                    amount,
                    self._sc_repo.count_by_organization,
                    "max_source_connections",
                )

            # Cumulative metrics (entities, queries) — cached with TTL
            should_refresh = (
                self.usage is None
                or self.usage_fetched_at is None
                or datetime.utcnow() - self.usage_fetched_at > _USAGE_CACHE_TTL
            )
            if should_refresh:
                self.usage = await self._get_usage(db)
                self.usage_fetched_at = datetime.utcnow()

            if self.usage_limit is None:
                self.usage_limit = await self._infer_usage_limit(db)

            current_value = getattr(self.usage, action_type.value, 0) if self.usage else 0
            pending = self.pending_increments.get(action_type, 0)
            total_usage = current_value + pending

            limit_field = f"max_{action_type.value}"
            limit = getattr(self.usage_limit, limit_field, None) if self.usage_limit else None

            if limit is None:
                return True

            if total_usage + amount > limit:
                self.logger.warning(
                    f"Usage limit exceeded for {action_type.value}: "
                    f"current={total_usage}, requested={amount}, limit={limit}"
                )
                raise UsageLimitExceededError(
                    action_type=action_type.value,
                    limit=limit,
                    current_usage=total_usage,
                )

            self.logger.debug(
                f"Usage check: {action_type.value} usage={total_usage}, "
                f"requested={amount}, limit={limit}"
            )
            return True

    async def increment(self, db: AsyncSession, action_type: ActionType, amount: int = 1) -> None:
        """Buffer an increment; flush to DB when threshold is reached."""
        if action_type in (ActionType.TEAM_MEMBERS, ActionType.SOURCE_CONNECTIONS):
            return

        async with self._lock:
            has_billing = await self._check_has_billing(db)
            if not has_billing:
                return

            self.pending_increments[action_type] = (
                self.pending_increments.get(action_type, 0) + amount
            )

            threshold = _FLUSH_THRESHOLDS.get(action_type, 1)
            if abs(self.pending_increments[action_type]) >= threshold:
                await self._flush_usage_internal(db, action_type)

    async def decrement(self, db: AsyncSession, action_type: ActionType, amount: int = 1) -> None:
        """Buffer a decrement; flush to DB when threshold is reached."""
        if action_type in (ActionType.TEAM_MEMBERS, ActionType.SOURCE_CONNECTIONS):
            return

        async with self._lock:
            self.pending_increments[action_type] = (
                self.pending_increments.get(action_type, 0) - amount
            )

            threshold = _FLUSH_THRESHOLDS.get(action_type, 1)
            if abs(self.pending_increments[action_type]) >= threshold:
                await self._flush_usage_internal(db, action_type)

    async def flush_all(self, db: AsyncSession) -> None:
        """Flush all pending increments — call before sync termination."""
        self.logger.info("Flushing all pending usage increments before termination")
        try:
            async with self._lock:
                await self._flush_usage_internal(db, action_type=None)
            self.logger.info("Successfully flushed all pending usage increments")
        except Exception as e:
            self.logger.error(f"Failed to flush usage increments: {str(e)}", exc_info=True)
            raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _check_has_billing(self, db: AsyncSession) -> bool:
        if self._has_billing is not None:
            return self._has_billing
        record = await self._billing_repo.get_by_org_id(db, organization_id=self.organization_id)
        self._has_billing = record is not None
        return self._has_billing

    async def _get_usage(self, db: AsyncSession) -> Optional[Usage]:
        usage_record = await self._usage_repo.get_current_usage(
            db, organization_id=self.organization_id
        )
        if usage_record:
            usage = Usage.model_validate(usage_record)
            usage.team_members = await self._user_org_repo.count_members(db, self.organization_id)
            usage.source_connections = await self._sc_repo.count_by_organization(
                db, self.organization_id
            )
            return usage
        return None

    async def _get_billing_status(self, db: AsyncSession) -> BillingPeriodStatus:
        current_period = await self._period_repo.get_current_period(
            db, organization_id=self.organization_id
        )
        if not current_period:
            self.logger.warning(
                f"Organization {self.organization_id} has billing but no active period. "
                "Defaulting to ACTIVE status."
            )
            return BillingPeriodStatus.ACTIVE
        if not current_period.status:
            return BillingPeriodStatus.ACTIVE
        # ORM stores status as a plain string; normalise to enum
        status = current_period.status
        if isinstance(status, str):
            return BillingPeriodStatus(status)
        return status

    async def _get_current_plan(self, db: AsyncSession) -> BillingPlan:
        current_period = await self._period_repo.get_current_period(
            db, organization_id=self.organization_id
        )
        if not current_period or not current_period.plan:
            return BillingPlan.DEVELOPER
        return current_period.plan

    async def _infer_usage_limit(self, db: AsyncSession) -> UsageLimit:
        current_period = await self._period_repo.get_current_period(
            db, organization_id=self.organization_id
        )
        if not current_period or not current_period.plan:
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
        return infer_usage_limit(plan)

    async def _check_dynamic_metric_allowed(
        self,
        db: AsyncSession,
        action_type: ActionType,
        amount: int,
        count_func,
        limit_field: str,
    ) -> bool:
        current_count = await count_func(db, self.organization_id)

        if self.usage_limit is None:
            self.usage_limit = await self._infer_usage_limit(db)

        max_limit = getattr(self.usage_limit, limit_field, None)
        if max_limit is None:
            return True

        if current_count + amount > max_limit:
            self.logger.warning(
                f"{action_type.value} limit exceeded: current={current_count}, "
                f"requested={amount}, limit={max_limit}"
            )
            raise UsageLimitExceededError(
                action_type=action_type.value,
                limit=max_limit,
                current_usage=current_count,
            )
        return True

    async def _flush_usage_internal(
        self, db: AsyncSession, action_type: Optional[ActionType] = None
    ) -> None:
        """Flush pending increments to the database.  Must be called under lock."""
        has_billing = await self._check_has_billing(db)
        if not has_billing:
            return

        if action_type is not None:
            if self.pending_increments.get(action_type, 0) == 0:
                return
            increments_to_flush = {action_type: self.pending_increments[action_type]}
        else:
            increments_to_flush = {
                at: count for at, count in self.pending_increments.items() if count != 0
            }

        if not increments_to_flush:
            return

        self.logger.info(f"Persisting usage increments to database: {increments_to_flush}")
        updated_usage_record = await self._usage_repo.increment_usage(
            db, organization_id=self.organization_id, increments=increments_to_flush
        )

        if updated_usage_record:
            self.usage = Usage.model_validate(updated_usage_record)
            self.usage.team_members = await self._user_org_repo.count_members(
                db, self.organization_id
            )
            self.usage.source_connections = await self._sc_repo.count_by_organization(
                db, self.organization_id
            )
            self.usage_fetched_at = datetime.utcnow()

        for at in increments_to_flush:
            self.pending_increments[at] = 0


class AlwaysAllowUsageGuardrailService(UsageGuardrailService):
    """Always allow usage guardrail service."""

    async def is_allowed(self, db: AsyncSession, action_type: ActionType, amount: int = 1) -> bool:
        """Always allow."""
        return True