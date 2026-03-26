"""Tests for BillingUnpauseSubscriber."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from airweave.core.events.billing import BillingPeriodCreatedEvent
from airweave.core.shared_models import SyncPauseReason, SyncStatus
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


def _make_sync(pause_reason: str, sync_id=None):
    s = MagicMock()
    s.id = sync_id or uuid4()
    s.status = SyncStatus.PAUSED.value
    s.pause_reason = pause_reason
    return s


def _make_subscriber(
    paused_syncs=None,
    org_schema=None,
):
    sync_state_machine = AsyncMock()
    sync_repo = AsyncMock()
    sync_repo.get_paused_by_reason = AsyncMock(return_value=paused_syncs or [])
    org_repo = AsyncMock()
    org_repo.get = AsyncMock(return_value=org_schema or MagicMock())

    subscriber = BillingUnpauseSubscriber(
        sync_state_machine=sync_state_machine,
        sync_repo=sync_repo,
        org_repo=org_repo,
    )
    return subscriber, sync_state_machine, sync_repo, org_repo


@pytest.mark.asyncio
async def test_unpauses_usage_exhausted_syncs():
    """Usage-exhausted syncs are unpaused."""
    usage_sync_1 = _make_sync(SyncPauseReason.USAGE_EXHAUSTED.value)
    usage_sync_2 = _make_sync(SyncPauseReason.USAGE_EXHAUSTED.value)

    subscriber, sync_state_machine, sync_repo, _ = _make_subscriber(
        paused_syncs=[usage_sync_1, usage_sync_2],
    )

    await subscriber.handle(_make_event())

    sync_repo.get_paused_by_reason.assert_awaited_once_with(
        sync_repo.get_paused_by_reason.call_args[0][0],  # db session
        organization_id=ORG_ID,
        pause_reason=SyncPauseReason.USAGE_EXHAUSTED.value,
    )
    assert sync_state_machine.transition.await_count == 2
    transitioned_ids = {
        call.kwargs["sync_id"] for call in sync_state_machine.transition.call_args_list
    }
    assert transitioned_ids == {usage_sync_1.id, usage_sync_2.id}


@pytest.mark.asyncio
async def test_grace_period_does_not_unpause():
    """Events with GRACE status do not trigger unpause."""
    subscriber, sync_state_machine, sync_repo, _ = _make_subscriber()

    await subscriber.handle(_make_event(status=BillingPeriodStatus.GRACE.value))

    sync_repo.get_paused_by_reason.assert_not_awaited()
    sync_state_machine.transition.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_paused_syncs_is_noop():
    """No paused syncs means no transitions attempted."""
    subscriber, sync_state_machine, _, _ = _make_subscriber(paused_syncs=[])

    await subscriber.handle(_make_event())

    sync_state_machine.transition.assert_not_awaited()


@pytest.mark.asyncio
async def test_unpause_failure_is_nonfatal():
    """If one sync fails to unpause, the others still get processed."""
    sync_1 = _make_sync(SyncPauseReason.USAGE_EXHAUSTED.value)
    sync_2 = _make_sync(SyncPauseReason.USAGE_EXHAUSTED.value)

    subscriber, sync_state_machine, _, _ = _make_subscriber(
        paused_syncs=[sync_1, sync_2],
    )
    sync_state_machine.transition.side_effect = [
        Exception("temporal down"),
        AsyncMock(),
    ]

    await subscriber.handle(_make_event())

    assert sync_state_machine.transition.await_count == 2


@pytest.mark.asyncio
async def test_org_not_found_returns_early():
    """If org not found, no syncs are queried or unpaused."""
    subscriber, sync_state_machine, sync_repo, org_repo = _make_subscriber()
    org_repo.get = AsyncMock(return_value=None)

    await subscriber.handle(_make_event())

    sync_repo.get_paused_by_reason.assert_not_awaited()
    sync_state_machine.transition.assert_not_awaited()
