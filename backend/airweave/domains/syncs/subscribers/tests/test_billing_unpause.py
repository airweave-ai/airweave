"""Tests for BillingUnpauseSubscriber."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
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


@pytest.mark.asyncio
async def test_unpauses_usage_exhausted_syncs_only():
    """Only syncs paused for USAGE_EXHAUSTED are unpaused."""
    usage_sync_1 = _make_sync(SyncPauseReason.USAGE_EXHAUSTED.value)
    usage_sync_2 = _make_sync(SyncPauseReason.USAGE_EXHAUSTED.value)
    cred_sync = _make_sync(SyncPauseReason.CREDENTIAL_ERROR.value)

    sync_state_machine = AsyncMock()
    subscriber = BillingUnpauseSubscriber(sync_state_machine=sync_state_machine)

    mock_org = MagicMock()
    mock_org.id = ORG_ID

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_org)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [usage_sync_1, usage_sync_2]
    mock_db.execute = AsyncMock(return_value=mock_result)

    with (
        patch(
            "airweave.domains.syncs.subscribers.billing_unpause.get_db_context"
        ) as mock_ctx,
        patch("airweave.domains.syncs.subscribers.billing_unpause.schemas") as mock_schemas,
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_schemas.Organization.model_validate.return_value = MagicMock()

        await subscriber.handle(_make_event())

    assert sync_state_machine.transition.await_count == 2
    transitioned_ids = {
        call.kwargs["sync_id"] for call in sync_state_machine.transition.call_args_list
    }
    assert transitioned_ids == {usage_sync_1.id, usage_sync_2.id}


@pytest.mark.asyncio
async def test_grace_period_does_not_unpause():
    """Events with GRACE status do not trigger unpause."""
    sync_state_machine = AsyncMock()
    subscriber = BillingUnpauseSubscriber(sync_state_machine=sync_state_machine)

    await subscriber.handle(_make_event(status=BillingPeriodStatus.GRACE.value))

    sync_state_machine.transition.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_paused_syncs_is_noop():
    """No paused syncs means no transitions attempted."""
    sync_state_machine = AsyncMock()
    subscriber = BillingUnpauseSubscriber(sync_state_machine=sync_state_machine)

    mock_org = MagicMock()
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_org)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    with (
        patch(
            "airweave.domains.syncs.subscribers.billing_unpause.get_db_context"
        ) as mock_ctx,
        patch("airweave.domains.syncs.subscribers.billing_unpause.schemas") as mock_schemas,
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_schemas.Organization.model_validate.return_value = MagicMock()

        await subscriber.handle(_make_event())

    sync_state_machine.transition.assert_not_awaited()


@pytest.mark.asyncio
async def test_unpause_failure_is_nonfatal():
    """If one sync fails to unpause, the others still get processed."""
    sync_1 = _make_sync(SyncPauseReason.USAGE_EXHAUSTED.value)
    sync_2 = _make_sync(SyncPauseReason.USAGE_EXHAUSTED.value)

    sync_state_machine = AsyncMock()
    sync_state_machine.transition.side_effect = [
        Exception("temporal down"),
        AsyncMock(),  # second call succeeds
    ]
    subscriber = BillingUnpauseSubscriber(sync_state_machine=sync_state_machine)

    mock_org = MagicMock()
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_org)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [sync_1, sync_2]
    mock_db.execute = AsyncMock(return_value=mock_result)

    with (
        patch(
            "airweave.domains.syncs.subscribers.billing_unpause.get_db_context"
        ) as mock_ctx,
        patch("airweave.domains.syncs.subscribers.billing_unpause.schemas") as mock_schemas,
    ):
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_schemas.Organization.model_validate.return_value = MagicMock()

        await subscriber.handle(_make_event())

    assert sync_state_machine.transition.await_count == 2
