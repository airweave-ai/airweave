"""Tests for BillingUnpauseSubscriber."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from airweave.core.events.billing import BillingPeriodCreatedEvent
from airweave.core.shared_models import SyncPauseReason
from airweave.domains.syncs.subscribers.billing_unpause import BillingUnpauseSubscriber
from airweave.schemas.billing_period import BillingPeriodStatus


ORG_ID = uuid4()


def _make_event(status: str = BillingPeriodStatus.ACTIVE.value) -> BillingPeriodCreatedEvent:
    return BillingPeriodCreatedEvent(
        organization_id=ORG_ID,
        billing_period_id=uuid4(),
        plan="pro",
        status=status,
        transition="renewal",
    )


def _make_sync(sync_id=None):
    s = MagicMock()
    s.id = sync_id or uuid4()
    return s


def _make_subscriber(paused_syncs=None, org_schema=None):
    sync_service = AsyncMock()
    sync_service.list_paused_by_reason = AsyncMock(return_value=paused_syncs or [])
    sync_service.resume = AsyncMock()
    org_repo = AsyncMock()
    org_repo.get = AsyncMock(return_value=org_schema or MagicMock())

    subscriber = BillingUnpauseSubscriber(
        sync_service=sync_service,
        org_repo=org_repo,
    )
    return subscriber, sync_service, org_repo


@pytest.mark.asyncio
async def test_unpauses_usage_exhausted_syncs():
    """Usage-exhausted syncs are unpaused via sync_service.resume."""
    sync_1 = _make_sync()
    sync_2 = _make_sync()

    subscriber, sync_service, _ = _make_subscriber(paused_syncs=[sync_1, sync_2])

    await subscriber.handle(_make_event())

    sync_service.list_paused_by_reason.assert_awaited_once()
    call_kwargs = sync_service.list_paused_by_reason.await_args.kwargs
    assert call_kwargs["organization_id"] == ORG_ID
    assert call_kwargs["pause_reason"] == SyncPauseReason.USAGE_EXHAUSTED

    assert sync_service.resume.await_count == 2
    resumed_ids = {call.args[0] for call in sync_service.resume.call_args_list}
    assert resumed_ids == {sync_1.id, sync_2.id}


@pytest.mark.asyncio
async def test_grace_period_does_not_unpause():
    """Events with GRACE status do not trigger unpause."""
    subscriber, sync_service, _ = _make_subscriber()

    await subscriber.handle(_make_event(status=BillingPeriodStatus.GRACE.value))

    sync_service.list_paused_by_reason.assert_not_awaited()
    sync_service.resume.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_paused_syncs_is_noop():
    """No paused syncs means no resume attempts."""
    subscriber, sync_service, _ = _make_subscriber(paused_syncs=[])

    await subscriber.handle(_make_event())

    sync_service.resume.assert_not_awaited()


@pytest.mark.asyncio
async def test_unpause_failure_is_nonfatal():
    """If one sync fails to resume, the others still get processed."""
    sync_1 = _make_sync()
    sync_2 = _make_sync()

    subscriber, sync_service, _ = _make_subscriber(paused_syncs=[sync_1, sync_2])
    sync_service.resume.side_effect = [Exception("temporal down"), None]

    await subscriber.handle(_make_event())

    assert sync_service.resume.await_count == 2


@pytest.mark.asyncio
async def test_org_not_found_returns_early():
    """If org not found, no syncs are queried or resumed."""
    subscriber, sync_service, org_repo = _make_subscriber()
    org_repo.get = AsyncMock(return_value=None)

    await subscriber.handle(_make_event())

    sync_service.list_paused_by_reason.assert_not_awaited()
    sync_service.resume.assert_not_awaited()
