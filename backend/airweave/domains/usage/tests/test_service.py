"""Unit tests for UsageGuardrailService."""

import pytest

from airweave.domains.usage.exceptions import PaymentRequiredError, UsageLimitExceededError
from airweave.domains.usage.service import NullUsageGuardrailService
from airweave.domains.usage.tests.conftest import (
    DEFAULT_ORG_ID,
    _make_billing_model,
    _make_period_model,
    _make_service,
    _make_usage_model,
)
from airweave.domains.usage.types import ActionType
from airweave.schemas.billing_period import BillingPeriodStatus
from airweave.schemas.organization_billing import BillingPlan


# ---------------------------------------------------------------------------
# Helper: seed a service with billing + period + usage
# ---------------------------------------------------------------------------

def _seeded_service(
    plan=BillingPlan.PRO,
    period_status=BillingPeriodStatus.ACTIVE,
    entities=0,
    queries=0,
    sc_count=0,
    member_count=1,
):
    svc, usage_repo, billing_repo, period_repo, sc_repo, user_org_repo = _make_service()
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
    return svc, usage_repo, billing_repo, period_repo, sc_repo, user_org_repo


# ---------------------------------------------------------------------------
# is_allowed — no billing (legacy org exemption)
# ---------------------------------------------------------------------------

class TestIsAllowedNoBilling:
    @pytest.mark.asyncio
    async def test_allows_when_no_billing_record(self, db):
        svc, *_ = _make_service()
        assert await svc.is_allowed(db, ActionType.ENTITIES) is True

    @pytest.mark.asyncio
    async def test_allows_queries_when_no_billing(self, db):
        svc, *_ = _make_service()
        assert await svc.is_allowed(db, ActionType.QUERIES) is True


# ---------------------------------------------------------------------------
# is_allowed — billing status restrictions
# ---------------------------------------------------------------------------

class TestBillingStatusRestrictions:
    @pytest.mark.asyncio
    async def test_active_allows_all(self, db):
        svc, *_ = _seeded_service(period_status=BillingPeriodStatus.ACTIVE)
        assert await svc.is_allowed(db, ActionType.ENTITIES) is True
        assert await svc.is_allowed(db, ActionType.QUERIES) is True
        assert await svc.is_allowed(db, ActionType.SOURCE_CONNECTIONS) is True

    @pytest.mark.asyncio
    async def test_trial_allows_all(self, db):
        svc, *_ = _seeded_service(period_status=BillingPeriodStatus.TRIAL)
        assert await svc.is_allowed(db, ActionType.ENTITIES) is True
        assert await svc.is_allowed(db, ActionType.QUERIES) is True

    @pytest.mark.asyncio
    async def test_grace_blocks_source_connections(self, db):
        svc, *_ = _seeded_service(period_status=BillingPeriodStatus.GRACE)
        with pytest.raises(PaymentRequiredError) as exc_info:
            await svc.is_allowed(db, ActionType.SOURCE_CONNECTIONS)
        assert exc_info.value.action_type == "source_connections"
        assert exc_info.value.payment_status == "grace"

    @pytest.mark.asyncio
    async def test_grace_allows_queries(self, db):
        svc, *_ = _seeded_service(period_status=BillingPeriodStatus.GRACE)
        assert await svc.is_allowed(db, ActionType.QUERIES) is True

    @pytest.mark.asyncio
    async def test_ended_unpaid_blocks_entities(self, db):
        svc, *_ = _seeded_service(period_status=BillingPeriodStatus.ENDED_UNPAID)
        with pytest.raises(PaymentRequiredError):
            await svc.is_allowed(db, ActionType.ENTITIES)

    @pytest.mark.asyncio
    async def test_ended_unpaid_blocks_source_connections(self, db):
        svc, *_ = _seeded_service(period_status=BillingPeriodStatus.ENDED_UNPAID)
        with pytest.raises(PaymentRequiredError):
            await svc.is_allowed(db, ActionType.SOURCE_CONNECTIONS)

    @pytest.mark.asyncio
    async def test_ended_unpaid_allows_queries(self, db):
        svc, *_ = _seeded_service(period_status=BillingPeriodStatus.ENDED_UNPAID)
        assert await svc.is_allowed(db, ActionType.QUERIES) is True

    @pytest.mark.asyncio
    async def test_completed_blocks_everything(self, db):
        svc, *_ = _seeded_service(period_status=BillingPeriodStatus.COMPLETED)
        with pytest.raises(PaymentRequiredError):
            await svc.is_allowed(db, ActionType.ENTITIES)
        with pytest.raises(PaymentRequiredError):
            await svc.is_allowed(db, ActionType.QUERIES)
        with pytest.raises(PaymentRequiredError):
            await svc.is_allowed(db, ActionType.SOURCE_CONNECTIONS)


# ---------------------------------------------------------------------------
# is_allowed — entity limits
# ---------------------------------------------------------------------------

class TestEntityLimits:
    @pytest.mark.asyncio
    async def test_allows_entities_under_limit(self, db):
        svc, *_ = _seeded_service(plan=BillingPlan.PRO, entities=50000)
        assert await svc.is_allowed(db, ActionType.ENTITIES) is True

    @pytest.mark.asyncio
    async def test_raises_at_entity_limit(self, db):
        svc, *_ = _seeded_service(plan=BillingPlan.PRO, entities=100000)
        with pytest.raises(UsageLimitExceededError) as exc_info:
            await svc.is_allowed(db, ActionType.ENTITIES)
        assert exc_info.value.action_type == "entities"
        assert exc_info.value.limit == 100000
        assert exc_info.value.current_usage == 100000

    @pytest.mark.asyncio
    async def test_enterprise_unlimited_entities(self, db):
        svc, *_ = _seeded_service(plan=BillingPlan.ENTERPRISE, entities=999999999)
        assert await svc.is_allowed(db, ActionType.ENTITIES) is True


# ---------------------------------------------------------------------------
# is_allowed — query limits
# ---------------------------------------------------------------------------

class TestQueryLimits:
    @pytest.mark.asyncio
    async def test_allows_queries_under_limit(self, db):
        svc, *_ = _seeded_service(plan=BillingPlan.PRO, queries=1000)
        assert await svc.is_allowed(db, ActionType.QUERIES) is True

    @pytest.mark.asyncio
    async def test_raises_at_query_limit(self, db):
        svc, *_ = _seeded_service(plan=BillingPlan.PRO, queries=2000)
        with pytest.raises(UsageLimitExceededError) as exc_info:
            await svc.is_allowed(db, ActionType.QUERIES)
        assert exc_info.value.action_type == "queries"
        assert exc_info.value.limit == 2000

    @pytest.mark.asyncio
    async def test_enterprise_unlimited_queries(self, db):
        svc, *_ = _seeded_service(plan=BillingPlan.ENTERPRISE, queries=999999999)
        assert await svc.is_allowed(db, ActionType.QUERIES) is True


# ---------------------------------------------------------------------------
# is_allowed — source connection limits (dynamic counting)
# ---------------------------------------------------------------------------

class TestSourceConnectionLimits:
    @pytest.mark.asyncio
    async def test_allows_under_limit(self, db):
        svc, *_ = _seeded_service(plan=BillingPlan.PRO, sc_count=30)
        assert await svc.is_allowed(db, ActionType.SOURCE_CONNECTIONS) is True

    @pytest.mark.asyncio
    async def test_raises_at_limit(self, db):
        svc, *_ = _seeded_service(plan=BillingPlan.PRO, sc_count=50)
        with pytest.raises(UsageLimitExceededError) as exc_info:
            await svc.is_allowed(db, ActionType.SOURCE_CONNECTIONS)
        assert exc_info.value.action_type == "source_connections"
        assert exc_info.value.limit == 50

    @pytest.mark.asyncio
    async def test_enterprise_unlimited(self, db):
        svc, *_ = _seeded_service(plan=BillingPlan.ENTERPRISE, sc_count=99999)
        assert await svc.is_allowed(db, ActionType.SOURCE_CONNECTIONS) is True


# ---------------------------------------------------------------------------
# is_allowed — team member limits (dynamic counting)
# ---------------------------------------------------------------------------

class TestTeamMemberLimits:
    @pytest.mark.asyncio
    async def test_allows_under_limit(self, db):
        svc, *_ = _seeded_service(plan=BillingPlan.PRO, member_count=1)
        assert await svc.is_allowed(db, ActionType.TEAM_MEMBERS) is True

    @pytest.mark.asyncio
    async def test_raises_at_limit(self, db):
        svc, *_ = _seeded_service(plan=BillingPlan.PRO, member_count=2)
        with pytest.raises(UsageLimitExceededError) as exc_info:
            await svc.is_allowed(db, ActionType.TEAM_MEMBERS)
        assert exc_info.value.action_type == "team_members"
        assert exc_info.value.limit == 2

    @pytest.mark.asyncio
    async def test_enterprise_unlimited(self, db):
        svc, *_ = _seeded_service(plan=BillingPlan.ENTERPRISE, member_count=1000)
        assert await svc.is_allowed(db, ActionType.TEAM_MEMBERS) is True


# ---------------------------------------------------------------------------
# increment — batching
# ---------------------------------------------------------------------------

class TestIncrement:
    @pytest.mark.asyncio
    async def test_entities_batch_to_threshold(self, db):
        """Entities are buffered until 100 pending."""
        svc, usage_repo, *_ = _seeded_service()
        for _ in range(99):
            await svc.increment(db, ActionType.ENTITIES)
        assert usage_repo.call_count("increment_usage") == 0
        await svc.increment(db, ActionType.ENTITIES)
        assert usage_repo.call_count("increment_usage") == 1

    @pytest.mark.asyncio
    async def test_queries_flush_immediately(self, db):
        """Queries flush after every increment (threshold=1)."""
        svc, usage_repo, *_ = _seeded_service()
        await svc.increment(db, ActionType.QUERIES)
        assert usage_repo.call_count("increment_usage") == 1

    @pytest.mark.asyncio
    async def test_skip_for_dynamic_types(self, db):
        """Team members and source connections are not tracked via increment."""
        svc, usage_repo, *_ = _seeded_service()
        await svc.increment(db, ActionType.TEAM_MEMBERS)
        await svc.increment(db, ActionType.SOURCE_CONNECTIONS)
        assert usage_repo.call_count("increment_usage") == 0

    @pytest.mark.asyncio
    async def test_skip_when_no_billing(self, db):
        """Increment is a no-op when the organization has no billing."""
        svc, usage_repo, *_ = _make_service()
        await svc.increment(db, ActionType.ENTITIES, 200)
        assert usage_repo.call_count("increment_usage") == 0


# ---------------------------------------------------------------------------
# decrement
# ---------------------------------------------------------------------------

class TestDecrement:
    @pytest.mark.asyncio
    async def test_decrement_accumulates(self, db):
        svc, usage_repo, *_ = _seeded_service()
        await svc.decrement(db, ActionType.ENTITIES, 50)
        assert svc.pending_increments[ActionType.ENTITIES] == -50
        assert usage_repo.call_count("increment_usage") == 0

    @pytest.mark.asyncio
    async def test_decrement_flushes_at_threshold(self, db):
        svc, usage_repo, *_ = _seeded_service(entities=200)
        await svc.decrement(db, ActionType.ENTITIES, 100)
        assert usage_repo.call_count("increment_usage") == 1

    @pytest.mark.asyncio
    async def test_skip_for_dynamic_types(self, db):
        svc, usage_repo, *_ = _seeded_service()
        await svc.decrement(db, ActionType.TEAM_MEMBERS)
        assert usage_repo.call_count("increment_usage") == 0


# ---------------------------------------------------------------------------
# flush_all
# ---------------------------------------------------------------------------

class TestFlushAll:
    @pytest.mark.asyncio
    async def test_flushes_all_pending(self, db):
        svc, usage_repo, *_ = _seeded_service()
        # Buffer some increments (below threshold so they don't auto-flush)
        await svc.increment(db, ActionType.ENTITIES, 50)
        assert usage_repo.call_count("increment_usage") == 0
        await svc.flush_all(db)
        assert usage_repo.call_count("increment_usage") == 1

    @pytest.mark.asyncio
    async def test_no_op_when_nothing_pending(self, db):
        svc, usage_repo, *_ = _seeded_service()
        await svc.flush_all(db)
        assert usage_repo.call_count("increment_usage") == 0


# ---------------------------------------------------------------------------
# NullUsageGuardrailService
# ---------------------------------------------------------------------------

class TestNullService:
    @pytest.mark.asyncio
    async def test_always_allows(self, db):
        svc = NullUsageGuardrailService()
        assert await svc.is_allowed(db, ActionType.ENTITIES) is True
        assert await svc.is_allowed(db, ActionType.QUERIES) is True
        assert await svc.is_allowed(db, ActionType.SOURCE_CONNECTIONS) is True
        assert await svc.is_allowed(db, ActionType.TEAM_MEMBERS) is True

    @pytest.mark.asyncio
    async def test_increment_is_noop(self, db):
        svc = NullUsageGuardrailService()
        await svc.increment(db, ActionType.ENTITIES, 1000)

    @pytest.mark.asyncio
    async def test_flush_all_is_noop(self, db):
        svc = NullUsageGuardrailService()
        await svc.flush_all(db)


# ---------------------------------------------------------------------------
# Developer plan limits
# ---------------------------------------------------------------------------

class TestDeveloperPlan:
    @pytest.mark.asyncio
    async def test_developer_entity_limit(self, db):
        svc, *_ = _seeded_service(plan=BillingPlan.DEVELOPER, entities=50000)
        with pytest.raises(UsageLimitExceededError) as exc_info:
            await svc.is_allowed(db, ActionType.ENTITIES)
        assert exc_info.value.limit == 50000

    @pytest.mark.asyncio
    async def test_developer_query_limit(self, db):
        svc, *_ = _seeded_service(plan=BillingPlan.DEVELOPER, queries=500)
        with pytest.raises(UsageLimitExceededError) as exc_info:
            await svc.is_allowed(db, ActionType.QUERIES)
        assert exc_info.value.limit == 500

    @pytest.mark.asyncio
    async def test_developer_source_connection_limit(self, db):
        svc, *_ = _seeded_service(plan=BillingPlan.DEVELOPER, sc_count=10)
        with pytest.raises(UsageLimitExceededError) as exc_info:
            await svc.is_allowed(db, ActionType.SOURCE_CONNECTIONS)
        assert exc_info.value.limit == 10

    @pytest.mark.asyncio
    async def test_developer_team_member_limit(self, db):
        svc, *_ = _seeded_service(plan=BillingPlan.DEVELOPER, member_count=1)
        with pytest.raises(UsageLimitExceededError) as exc_info:
            await svc.is_allowed(db, ActionType.TEAM_MEMBERS)
        assert exc_info.value.limit == 1


# ---------------------------------------------------------------------------
# Team plan limits
# ---------------------------------------------------------------------------

class TestTeamPlan:
    @pytest.mark.asyncio
    async def test_team_entity_limit(self, db):
        svc, *_ = _seeded_service(plan=BillingPlan.TEAM, entities=999999)
        assert await svc.is_allowed(db, ActionType.ENTITIES) is True

    @pytest.mark.asyncio
    async def test_team_entity_limit_exceeded(self, db):
        svc, *_ = _seeded_service(plan=BillingPlan.TEAM, entities=1000000)
        with pytest.raises(UsageLimitExceededError) as exc_info:
            await svc.is_allowed(db, ActionType.ENTITIES)
        assert exc_info.value.limit == 1000000
