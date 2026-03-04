"""Usage limit checker — singleton read-only enforcement service.

One instance lives in the container. Each ``is_allowed()`` call receives
the ``organization_id`` as a parameter; billing status and usage data are
cached per-org with a short TTL.

SOURCE_CONNECTIONS and TEAM_MEMBERS always query live counts.
ENTITIES and QUERIES accept cached usage data (30s TTL).
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.domains.billing.repository import (
    BillingPeriodRepositoryProtocol,
    OrganizationBillingRepositoryProtocol,
)
from airweave.domains.organizations.protocols import UserOrganizationRepositoryProtocol
from airweave.domains.source_connections.protocols import SourceConnectionRepositoryProtocol
from airweave.domains.usage.exceptions import PaymentRequiredError, UsageLimitExceededError
from airweave.domains.usage.protocols import UsageLimitCheckerProtocol
from airweave.domains.usage.repository import UsageRepositoryProtocol
from airweave.domains.usage.types import (
    BILLING_STATUS_RESTRICTIONS,
    ActionType,
    infer_usage_limit,
)
from airweave.schemas.billing_period import BillingPeriodStatus
from airweave.schemas.organization_billing import BillingPlan
from airweave.schemas.usage import Usage, UsageLimit

_USAGE_CACHE_TTL = timedelta(seconds=15)

_FRESH_ACTION_TYPES: frozenset[ActionType] = frozenset(
    {ActionType.SOURCE_CONNECTIONS, ActionType.TEAM_MEMBERS}
)


class _OrgCache:
    """Short-lived per-org cache entry."""

    __slots__ = ("has_billing", "usage", "usage_limit", "fetched_at")

    def __init__(self) -> None:
        self.has_billing: Optional[bool] = None
        self.usage: Optional[Usage] = None
        self.usage_limit: Optional[UsageLimit] = None
        self.fetched_at: Optional[datetime] = None

    @property
    def is_stale(self) -> bool:
        return self.fetched_at is None or datetime.now(UTC) - self.fetched_at > _USAGE_CACHE_TTL


class UsageLimitChecker(UsageLimitCheckerProtocol):
    """Singleton limit checker with per-org TTL cache."""

    def __init__(
        self,
        usage_repo: UsageRepositoryProtocol,
        billing_repo: OrganizationBillingRepositoryProtocol,
        period_repo: BillingPeriodRepositoryProtocol,
        sc_repo: SourceConnectionRepositoryProtocol,
        user_org_repo: UserOrganizationRepositoryProtocol,
    ) -> None:
        """Initialize the checker with repository dependencies."""
        self._usage_repo = usage_repo
        self._billing_repo = billing_repo
        self._period_repo = period_repo
        self._sc_repo = sc_repo
        self._user_org_repo = user_org_repo

        self._cache: dict[UUID, _OrgCache] = {}
        self._lock = asyncio.Lock()

    def _get_cache(self, org_id: UUID) -> _OrgCache:
        if org_id not in self._cache:
            self._cache[org_id] = _OrgCache()
        return self._cache[org_id]

    async def is_allowed(
        self,
        db: AsyncSession,
        organization_id: UUID,
        action_type: ActionType,
        amount: int = 1,
    ) -> bool:
        """Check if the action is allowed under usage limits."""
        async with self._lock:
            cache = self._get_cache(organization_id)

            has_billing = await self._check_has_billing(db, organization_id, cache)
            if not has_billing:
                return True

            billing_status = await self._get_billing_status(db, organization_id)
            restricted = BILLING_STATUS_RESTRICTIONS.get(billing_status, set())
            if action_type in restricted:
                raise PaymentRequiredError(
                    action_type=action_type.value,
                    payment_status=billing_status.value,
                )

            if action_type in _FRESH_ACTION_TYPES:
                return await self._check_dynamic(db, organization_id, action_type, amount, cache)

            if cache.is_stale:
                cache.usage = await self._get_usage(db, organization_id)
                cache.fetched_at = datetime.now(UTC)

            if cache.usage_limit is None:
                cache.usage_limit = await self._infer_limit(db, organization_id)

            current = getattr(cache.usage, action_type.value, 0) if cache.usage else 0
            limit_field = f"max_{action_type.value}"
            limit = getattr(cache.usage_limit, limit_field, None) if cache.usage_limit else None

            if limit is None:
                return True

            if current + amount > limit:
                raise UsageLimitExceededError(
                    action_type=action_type.value,
                    limit=limit,
                    current_usage=current,
                )
            return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _check_has_billing(self, db: AsyncSession, org_id: UUID, cache: _OrgCache) -> bool:
        if cache.has_billing is not None:
            return cache.has_billing
        record = await self._billing_repo.get_by_org_id(db, organization_id=org_id)
        cache.has_billing = record is not None
        return cache.has_billing

    async def _get_usage(self, db: AsyncSession, org_id: UUID) -> Optional[Usage]:
        usage_record = await self._usage_repo.get_current_usage(db, organization_id=org_id)
        if usage_record:
            usage = Usage.model_validate(usage_record)
            usage.team_members = await self._user_org_repo.count_members(db, org_id)
            usage.source_connections = await self._sc_repo.count_by_organization(db, org_id)
            return usage
        return None

    async def _get_billing_status(self, db: AsyncSession, org_id: UUID) -> BillingPeriodStatus:
        current_period = await self._period_repo.get_current_period(db, organization_id=org_id)
        if not current_period or not current_period.status:
            return BillingPeriodStatus.ACTIVE
        status = current_period.status
        if isinstance(status, str):
            return BillingPeriodStatus(status)
        return status

    async def _infer_limit(self, db: AsyncSession, org_id: UUID) -> UsageLimit:
        current_period = await self._period_repo.get_current_period(db, organization_id=org_id)
        if not current_period or not current_period.plan:
            return infer_usage_limit(BillingPlan.DEVELOPER)
        try:
            plan = (
                current_period.plan
                if hasattr(current_period.plan, "value")
                else BillingPlan(str(current_period.plan))
            )
        except Exception:
            plan = BillingPlan.DEVELOPER
        return infer_usage_limit(plan)

    async def _check_dynamic(
        self,
        db: AsyncSession,
        org_id: UUID,
        action_type: ActionType,
        amount: int,
        cache: _OrgCache,
    ) -> bool:
        if action_type == ActionType.TEAM_MEMBERS:
            current = await self._user_org_repo.count_members(db, org_id)
            limit_field = "max_team_members"
        elif action_type == ActionType.SOURCE_CONNECTIONS:
            current = await self._sc_repo.count_by_organization(db, org_id)
            limit_field = "max_source_connections"
        else:
            return True

        if cache.usage_limit is None:
            cache.usage_limit = await self._infer_limit(db, org_id)

        max_limit = getattr(cache.usage_limit, limit_field, None)
        if max_limit is None:
            return True

        if current + amount > max_limit:
            raise UsageLimitExceededError(
                action_type=action_type.value,
                limit=max_limit,
                current_usage=current,
            )
        return True


class AlwaysAllowLimitChecker(UsageLimitCheckerProtocol):
    """No-op checker for local development."""

    async def is_allowed(
        self,
        db: AsyncSession,
        organization_id: UUID,
        action_type: ActionType,
        amount: int = 1,
    ) -> bool:
        """Always allow; no enforcement."""
        return True
