"""Unit tests for UsageLimitCheckService."""

import pytest

from airweave.domains.usage.exceptions import PaymentRequiredError, UsageLimitExceededError
from airweave.domains.usage.limit_checker import AlwaysAllowLimitChecker
from airweave.domains.usage.tests.conftest import (
    DEFAULT_ORG_ID,
    _make_billing_model,
    _make_checker,
    _make_period_model,
    _make_usage_model,
)
from airweave.domains.usage.types import ActionType
from airweave.schemas.billing_period import BillingPeriodStatus
from airweave.schemas.organization_billing import BillingPlan


# ---------------------------------------------------------------------------
# Helper: seed a checker with billing + period + usage
# ---------------------------------------------------------------------------

def _seeded_checker(
    plan=BillingPlan.PRO,
    period_status=BillingPeriodStatus.ACTIVE,
    entities=0,
    queries=0,
    sc_count=0,
    member_count=1,
):
    checker, usage_repo, billing_repo, period_repo, sc_repo, user_org_repo = _make_checker()
    billing = _make_billing_model(billing_plan=plan.value)
    billing_repo.seed(DEFAULT_ORG_ID, billing)
    period = _make_period_model(plan=plan.value, status=period_status.value)
    period_repo.seed(period)
    usage = _make_usage_model(
        org_id=DEFAULT_ORG_ID,
        billing_period_id=period.id,
        entities=entities,
        queries=queries,
    )
    usage_repo.seed_current(DEFAULT_ORG_ID, usage)
    sc_repo.set_org_count(DEFAULT_ORG_ID, sc_count)
    user_org_repo.set_count(DEFAULT_ORG_ID, member_count)
    return checker, usage_repo, billing_repo, period_repo, sc_repo, user_org_repo


# ---------------------------------------------------------------------------
# is_allowed — no billing (legacy org exemption)
# ---------------------------------------------------------------------------

class TestIsAllowedNoBilling:
    @pytest.mark.asyncio
    async def test_allows_when_no_billing_record(self, db):
        checker, *_ = _make_checker()
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.ENTITIES) is True

    @pytest.mark.asyncio
    async def test_allows_queries_when_no_billing(self, db):
        checker, *_ = _make_checker()
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.QUERIES) is True


# ---------------------------------------------------------------------------
# is_allowed — billing status restrictions
# ---------------------------------------------------------------------------

class TestBillingStatusRestrictions:
    @pytest.mark.asyncio
    async def test_active_allows_all(self, db):
        checker, *_ = _seeded_checker(period_status=BillingPeriodStatus.ACTIVE)
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.ENTITIES) is True
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.QUERIES) is True
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.SOURCE_CONNECTIONS) is True

    @pytest.mark.asyncio
    async def test_trial_allows_all(self, db):
        checker, *_ = _seeded_checker(period_status=BillingPeriodStatus.TRIAL)
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.ENTITIES) is True
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.QUERIES) is True

    @pytest.mark.asyncio
    async def test_grace_blocks_source_connections(self, db):
        checker, *_ = _seeded_checker(period_status=BillingPeriodStatus.GRACE)
        with pytest.raises(PaymentRequiredError) as exc_info:
            await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.SOURCE_CONNECTIONS)
        assert exc_info.value.action_type == "source_connections"
        assert exc_info.value.payment_status == "grace"

    @pytest.mark.asyncio
    async def test_grace_allows_queries(self, db):
        checker, *_ = _seeded_checker(period_status=BillingPeriodStatus.GRACE)
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.QUERIES) is True

    @pytest.mark.asyncio
    async def test_ended_unpaid_blocks_entities(self, db):
        checker, *_ = _seeded_checker(period_status=BillingPeriodStatus.ENDED_UNPAID)
        with pytest.raises(PaymentRequiredError):
            await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.ENTITIES)

    @pytest.mark.asyncio
    async def test_ended_unpaid_blocks_source_connections(self, db):
        checker, *_ = _seeded_checker(period_status=BillingPeriodStatus.ENDED_UNPAID)
        with pytest.raises(PaymentRequiredError):
            await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.SOURCE_CONNECTIONS)

    @pytest.mark.asyncio
    async def test_ended_unpaid_allows_queries(self, db):
        checker, *_ = _seeded_checker(period_status=BillingPeriodStatus.ENDED_UNPAID)
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.QUERIES) is True

    @pytest.mark.asyncio
    async def test_completed_blocks_everything(self, db):
        checker, *_ = _seeded_checker(period_status=BillingPeriodStatus.COMPLETED)
        with pytest.raises(PaymentRequiredError):
            await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.ENTITIES)
        with pytest.raises(PaymentRequiredError):
            await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.QUERIES)
        with pytest.raises(PaymentRequiredError):
            await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.SOURCE_CONNECTIONS)


# ---------------------------------------------------------------------------
# is_allowed — entity limits
# ---------------------------------------------------------------------------

class TestEntityLimits:
    @pytest.mark.asyncio
    async def test_allows_entities_under_limit(self, db):
        checker, *_ = _seeded_checker(plan=BillingPlan.PRO, entities=50000)
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.ENTITIES) is True

    @pytest.mark.asyncio
    async def test_raises_at_entity_limit(self, db):
        checker, *_ = _seeded_checker(plan=BillingPlan.PRO, entities=100000)
        with pytest.raises(UsageLimitExceededError) as exc_info:
            await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.ENTITIES)
        assert exc_info.value.action_type == "entities"
        assert exc_info.value.limit == 100000
        assert exc_info.value.current_usage == 100000

    @pytest.mark.asyncio
    async def test_enterprise_unlimited_entities(self, db):
        checker, *_ = _seeded_checker(plan=BillingPlan.ENTERPRISE, entities=999999999)
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.ENTITIES) is True


# ---------------------------------------------------------------------------
# is_allowed — query limits
# ---------------------------------------------------------------------------

class TestQueryLimits:
    @pytest.mark.asyncio
    async def test_allows_queries_under_limit(self, db):
        checker, *_ = _seeded_checker(plan=BillingPlan.PRO, queries=1000)
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.QUERIES) is True

    @pytest.mark.asyncio
    async def test_raises_at_query_limit(self, db):
        checker, *_ = _seeded_checker(plan=BillingPlan.PRO, queries=2000)
        with pytest.raises(UsageLimitExceededError) as exc_info:
            await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.QUERIES)
        assert exc_info.value.action_type == "queries"
        assert exc_info.value.limit == 2000

    @pytest.mark.asyncio
    async def test_enterprise_unlimited_queries(self, db):
        checker, *_ = _seeded_checker(plan=BillingPlan.ENTERPRISE, queries=999999999)
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.QUERIES) is True


# ---------------------------------------------------------------------------
# is_allowed — source connection limits (dynamic counting)
# ---------------------------------------------------------------------------

class TestSourceConnectionLimits:
    @pytest.mark.asyncio
    async def test_allows_under_limit(self, db):
        checker, *_ = _seeded_checker(plan=BillingPlan.PRO, sc_count=30)
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.SOURCE_CONNECTIONS) is True

    @pytest.mark.asyncio
    async def test_raises_at_limit(self, db):
        checker, *_ = _seeded_checker(plan=BillingPlan.PRO, sc_count=50)
        with pytest.raises(UsageLimitExceededError) as exc_info:
            await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.SOURCE_CONNECTIONS)
        assert exc_info.value.action_type == "source_connections"
        assert exc_info.value.limit == 50

    @pytest.mark.asyncio
    async def test_enterprise_unlimited(self, db):
        checker, *_ = _seeded_checker(plan=BillingPlan.ENTERPRISE, sc_count=99999)
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.SOURCE_CONNECTIONS) is True


# ---------------------------------------------------------------------------
# is_allowed — team member limits (dynamic counting)
# ---------------------------------------------------------------------------

class TestTeamMemberLimits:
    @pytest.mark.asyncio
    async def test_allows_under_limit(self, db):
        checker, *_ = _seeded_checker(plan=BillingPlan.PRO, member_count=1)
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.TEAM_MEMBERS) is True

    @pytest.mark.asyncio
    async def test_raises_at_limit(self, db):
        checker, *_ = _seeded_checker(plan=BillingPlan.PRO, member_count=2)
        with pytest.raises(UsageLimitExceededError) as exc_info:
            await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.TEAM_MEMBERS)
        assert exc_info.value.action_type == "team_members"
        assert exc_info.value.limit == 2

    @pytest.mark.asyncio
    async def test_enterprise_unlimited(self, db):
        checker, *_ = _seeded_checker(plan=BillingPlan.ENTERPRISE, member_count=1000)
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.TEAM_MEMBERS) is True


# ---------------------------------------------------------------------------
# AlwaysAllowLimitChecker
# ---------------------------------------------------------------------------

class TestAlwaysAllowChecker:
    @pytest.mark.asyncio
    async def test_always_allows(self, db):
        checker = AlwaysAllowLimitChecker()
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.ENTITIES) is True
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.QUERIES) is True
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.SOURCE_CONNECTIONS) is True
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.TEAM_MEMBERS) is True


# ---------------------------------------------------------------------------
# Developer plan limits
# ---------------------------------------------------------------------------

class TestDeveloperPlan:
    @pytest.mark.asyncio
    async def test_developer_entity_limit(self, db):
        checker, *_ = _seeded_checker(plan=BillingPlan.DEVELOPER, entities=50000)
        with pytest.raises(UsageLimitExceededError) as exc_info:
            await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.ENTITIES)
        assert exc_info.value.limit == 50000

    @pytest.mark.asyncio
    async def test_developer_query_limit(self, db):
        checker, *_ = _seeded_checker(plan=BillingPlan.DEVELOPER, queries=500)
        with pytest.raises(UsageLimitExceededError) as exc_info:
            await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.QUERIES)
        assert exc_info.value.limit == 500

    @pytest.mark.asyncio
    async def test_developer_source_connection_limit(self, db):
        checker, *_ = _seeded_checker(plan=BillingPlan.DEVELOPER, sc_count=10)
        with pytest.raises(UsageLimitExceededError) as exc_info:
            await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.SOURCE_CONNECTIONS)
        assert exc_info.value.limit == 10

    @pytest.mark.asyncio
    async def test_developer_team_member_limit(self, db):
        checker, *_ = _seeded_checker(plan=BillingPlan.DEVELOPER, member_count=1)
        with pytest.raises(UsageLimitExceededError) as exc_info:
            await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.TEAM_MEMBERS)
        assert exc_info.value.limit == 1


# ---------------------------------------------------------------------------
# Team plan limits
# ---------------------------------------------------------------------------

class TestTeamPlan:
    @pytest.mark.asyncio
    async def test_team_entity_limit(self, db):
        checker, *_ = _seeded_checker(plan=BillingPlan.TEAM, entities=999999)
        assert await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.ENTITIES) is True

    @pytest.mark.asyncio
    async def test_team_entity_limit_exceeded(self, db):
        checker, *_ = _seeded_checker(plan=BillingPlan.TEAM, entities=1000000)
        with pytest.raises(UsageLimitExceededError) as exc_info:
            await checker.is_allowed(db, DEFAULT_ORG_ID, ActionType.ENTITIES)
        assert exc_info.value.limit == 1000000
