"""Unit tests for UsageLedger — accumulation, threshold flushing, and explicit flush."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest

from airweave.domains.billing.fakes.repository import (
    FakeBillingPeriodRepository,
    FakeOrganizationBillingRepository,
)
from airweave.domains.usage.fakes.repository import FakeUsageRepository
from airweave.domains.usage.ledger import NullUsageLedger, UsageLedger, _FLUSH_THRESHOLDS
from airweave.domains.usage.tests.conftest import (
    DEFAULT_ORG_ID,
    _make_billing_model,
    _make_period_model,
    _make_usage_model,
)
from airweave.domains.usage.types import ActionType

OTHER_ORG_ID = UUID("00000000-0000-0000-0000-000000000002")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _fake_db_context():
    yield AsyncMock()


def _make_ledger(
    *,
    usage_repo=None,
    billing_repo=None,
    period_repo=None,
    seed_billing: bool = True,
):
    """Build a UsageLedger wired to fakes. Optionally seeds a billing record."""
    ur = usage_repo or FakeUsageRepository()
    br = billing_repo or FakeOrganizationBillingRepository()
    pr = period_repo or FakeBillingPeriodRepository()

    if seed_billing:
        billing = _make_billing_model()
        br.seed(DEFAULT_ORG_ID, billing)
        period = _make_period_model()
        pr.seed(period)
        usage = _make_usage_model(billing_period_id=period.id)
        ur.seed_current(DEFAULT_ORG_ID, usage)

    ledger = UsageLedger(usage_repo=ur, billing_repo=br, period_repo=pr)
    return ledger, ur, br, pr


# ---------------------------------------------------------------------------
# record — accumulation without flush
# ---------------------------------------------------------------------------


@patch("airweave.db.session.get_db_context", _fake_db_context)
class TestRecordAccumulation:
    @pytest.mark.asyncio
    async def test_accumulates_below_entity_threshold(self):
        ledger, usage_repo, *_ = _make_ledger()
        amount = _FLUSH_THRESHOLDS[ActionType.ENTITIES] - 1

        await ledger.record(DEFAULT_ORG_ID, ActionType.ENTITIES, amount=amount)

        assert ledger._accumulators[DEFAULT_ORG_ID][ActionType.ENTITIES] == amount
        assert usage_repo.call_count("increment_usage") == 0

    @pytest.mark.asyncio
    async def test_accumulates_below_query_threshold(self):
        ledger, usage_repo, *_ = _make_ledger()
        amount = _FLUSH_THRESHOLDS[ActionType.QUERIES] - 1

        await ledger.record(DEFAULT_ORG_ID, ActionType.QUERIES, amount=amount)

        assert ledger._accumulators[DEFAULT_ORG_ID][ActionType.QUERIES] == amount
        assert usage_repo.call_count("increment_usage") == 0

    @pytest.mark.asyncio
    async def test_multiple_small_records_accumulate(self):
        ledger, usage_repo, *_ = _make_ledger()

        await ledger.record(DEFAULT_ORG_ID, ActionType.ENTITIES, amount=10)
        await ledger.record(DEFAULT_ORG_ID, ActionType.ENTITIES, amount=20)
        await ledger.record(DEFAULT_ORG_ID, ActionType.ENTITIES, amount=30)

        assert ledger._accumulators[DEFAULT_ORG_ID][ActionType.ENTITIES] == 60
        assert usage_repo.call_count("increment_usage") == 0


# ---------------------------------------------------------------------------
# record — threshold-based auto-flush
# ---------------------------------------------------------------------------


@patch("airweave.db.session.get_db_context", _fake_db_context)
class TestRecordAutoFlush:
    @pytest.mark.asyncio
    async def test_flushes_at_entity_threshold(self):
        ledger, usage_repo, *_ = _make_ledger()
        threshold = _FLUSH_THRESHOLDS[ActionType.ENTITIES]

        await ledger.record(DEFAULT_ORG_ID, ActionType.ENTITIES, amount=threshold)

        assert usage_repo.call_count("increment_usage") == 1
        assert ledger._accumulators[DEFAULT_ORG_ID][ActionType.ENTITIES] == 0

    @pytest.mark.asyncio
    async def test_flushes_at_query_threshold(self):
        ledger, usage_repo, *_ = _make_ledger()
        threshold = _FLUSH_THRESHOLDS[ActionType.QUERIES]

        await ledger.record(DEFAULT_ORG_ID, ActionType.QUERIES, amount=threshold)

        assert usage_repo.call_count("increment_usage") == 1
        assert ledger._accumulators[DEFAULT_ORG_ID][ActionType.QUERIES] == 0

    @pytest.mark.asyncio
    async def test_flushes_over_threshold(self):
        ledger, usage_repo, *_ = _make_ledger()
        threshold = _FLUSH_THRESHOLDS[ActionType.ENTITIES]

        await ledger.record(DEFAULT_ORG_ID, ActionType.ENTITIES, amount=threshold + 50)

        assert usage_repo.call_count("increment_usage") == 1

    @pytest.mark.asyncio
    async def test_incremental_accumulation_triggers_flush(self):
        """Multiple small records that cumulatively hit the threshold."""
        ledger, usage_repo, *_ = _make_ledger()
        threshold = _FLUSH_THRESHOLDS[ActionType.QUERIES]

        for _ in range(threshold):
            await ledger.record(DEFAULT_ORG_ID, ActionType.QUERIES, amount=1)

        assert usage_repo.call_count("increment_usage") == 1
        assert ledger._accumulators[DEFAULT_ORG_ID][ActionType.QUERIES] == 0


# ---------------------------------------------------------------------------
# record — skipped action types
# ---------------------------------------------------------------------------


@patch("airweave.db.session.get_db_context", _fake_db_context)
class TestRecordSkippedActions:
    @pytest.mark.asyncio
    async def test_ignores_team_members(self):
        ledger, usage_repo, *_ = _make_ledger()

        await ledger.record(DEFAULT_ORG_ID, ActionType.TEAM_MEMBERS, amount=5)

        assert DEFAULT_ORG_ID not in ledger._accumulators
        assert usage_repo.call_count("increment_usage") == 0

    @pytest.mark.asyncio
    async def test_ignores_source_connections(self):
        ledger, usage_repo, *_ = _make_ledger()

        await ledger.record(DEFAULT_ORG_ID, ActionType.SOURCE_CONNECTIONS, amount=3)

        assert DEFAULT_ORG_ID not in ledger._accumulators
        assert usage_repo.call_count("increment_usage") == 0


# ---------------------------------------------------------------------------
# record — no billing record
# ---------------------------------------------------------------------------


@patch("airweave.db.session.get_db_context", _fake_db_context)
class TestRecordNoBilling:
    @pytest.mark.asyncio
    async def test_skips_when_no_billing(self):
        ledger, usage_repo, *_ = _make_ledger(seed_billing=False)

        await ledger.record(DEFAULT_ORG_ID, ActionType.ENTITIES, amount=500)

        assert DEFAULT_ORG_ID not in ledger._accumulators
        assert usage_repo.call_count("increment_usage") == 0

    @pytest.mark.asyncio
    async def test_caches_billing_check(self):
        """Second call for same org uses cached result."""
        ledger, _, billing_repo, _ = _make_ledger(seed_billing=False)

        await ledger.record(DEFAULT_ORG_ID, ActionType.ENTITIES, amount=1)
        await ledger.record(DEFAULT_ORG_ID, ActionType.ENTITIES, amount=1)

        get_calls = [c for c in billing_repo._calls if c[0] == "get_by_org_id"]
        assert len(get_calls) == 1


# ---------------------------------------------------------------------------
# explicit flush
# ---------------------------------------------------------------------------


@patch("airweave.db.session.get_db_context", _fake_db_context)
class TestExplicitFlush:
    @pytest.mark.asyncio
    async def test_flush_writes_pending(self):
        ledger, usage_repo, *_ = _make_ledger()
        await ledger.record(DEFAULT_ORG_ID, ActionType.ENTITIES, amount=5)
        await ledger.record(DEFAULT_ORG_ID, ActionType.QUERIES, amount=3)

        await ledger.flush(DEFAULT_ORG_ID)

        assert usage_repo.call_count("increment_usage") == 1
        assert ledger._accumulators[DEFAULT_ORG_ID][ActionType.ENTITIES] == 0
        assert ledger._accumulators[DEFAULT_ORG_ID][ActionType.QUERIES] == 0

    @pytest.mark.asyncio
    async def test_flush_all_orgs(self):
        ledger, usage_repo, billing_repo, period_repo = _make_ledger()

        other_billing = _make_billing_model(org_id=OTHER_ORG_ID)
        billing_repo.seed(OTHER_ORG_ID, other_billing)
        other_period = _make_period_model(org_id=OTHER_ORG_ID)
        period_repo.seed(other_period)
        other_usage = _make_usage_model(
            org_id=OTHER_ORG_ID, billing_period_id=other_period.id
        )
        usage_repo.seed_current(OTHER_ORG_ID, other_usage)

        await ledger.record(DEFAULT_ORG_ID, ActionType.ENTITIES, amount=5)
        await ledger.record(OTHER_ORG_ID, ActionType.QUERIES, amount=3)

        await ledger.flush()

        assert usage_repo.call_count("increment_usage") == 2

    @pytest.mark.asyncio
    async def test_flush_noop_when_empty(self):
        ledger, usage_repo, *_ = _make_ledger()

        await ledger.flush(DEFAULT_ORG_ID)

        assert usage_repo.call_count("increment_usage") == 0

    @pytest.mark.asyncio
    async def test_flush_scoped_to_org(self):
        """Flushing one org leaves the other's accumulator intact."""
        ledger, usage_repo, billing_repo, period_repo = _make_ledger()

        other_billing = _make_billing_model(org_id=OTHER_ORG_ID)
        billing_repo.seed(OTHER_ORG_ID, other_billing)
        other_period = _make_period_model(org_id=OTHER_ORG_ID)
        period_repo.seed(other_period)
        other_usage = _make_usage_model(
            org_id=OTHER_ORG_ID, billing_period_id=other_period.id
        )
        usage_repo.seed_current(OTHER_ORG_ID, other_usage)

        await ledger.record(DEFAULT_ORG_ID, ActionType.ENTITIES, amount=5)
        await ledger.record(OTHER_ORG_ID, ActionType.ENTITIES, amount=7)

        await ledger.flush(DEFAULT_ORG_ID)

        assert usage_repo.call_count("increment_usage") == 1
        assert ledger._accumulators[OTHER_ORG_ID][ActionType.ENTITIES] == 7


# ---------------------------------------------------------------------------
# NullUsageLedger
# ---------------------------------------------------------------------------


class TestNullUsageLedger:
    @pytest.mark.asyncio
    async def test_record_is_noop(self):
        ledger = NullUsageLedger()
        await ledger.record(DEFAULT_ORG_ID, ActionType.ENTITIES, amount=100)

    @pytest.mark.asyncio
    async def test_flush_is_noop(self):
        ledger = NullUsageLedger()
        await ledger.flush(DEFAULT_ORG_ID)
        await ledger.flush()
