"""Tests for SyncStateMachine — transition validation, idempotency, side effects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from airweave.core.shared_models import SyncPauseReason, SyncStatus
from airweave.domains.syncs.sync_state_machine import SyncStateMachine
from airweave.domains.syncs.types import InvalidSyncTransitionError, SyncTransitionResult

ORG_ID = uuid4()
SYNC_ID = uuid4()


def _make_sync_obj(status: SyncStatus) -> MagicMock:
    obj = MagicMock()
    obj.status = status.value
    return obj


def _make_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.organization = MagicMock()
    ctx.organization.id = ORG_ID
    return ctx


def _build_sm(
    sync_repo: Optional[AsyncMock] = None,
    schedule_svc: Optional[AsyncMock] = None,
) -> SyncStateMachine:
    return SyncStateMachine(
        sync_repo=sync_repo or AsyncMock(),
        temporal_schedule_service=schedule_svc or AsyncMock(),
    )


# ---------------------------------------------------------------------------
# Transition table tests
# ---------------------------------------------------------------------------


@dataclass
class TransitionCase:
    name: str
    current: SyncStatus
    target: SyncStatus
    valid: bool


TRANSITION_CASES = [
    TransitionCase("active_to_paused", SyncStatus.ACTIVE, SyncStatus.PAUSED, True),
    TransitionCase("active_to_inactive", SyncStatus.ACTIVE, SyncStatus.INACTIVE, True),
    TransitionCase("paused_to_active", SyncStatus.PAUSED, SyncStatus.ACTIVE, True),
    TransitionCase("inactive_to_active", SyncStatus.INACTIVE, SyncStatus.ACTIVE, True),
    TransitionCase("error_to_active", SyncStatus.ERROR, SyncStatus.ACTIVE, True),
    TransitionCase("error_to_paused", SyncStatus.ERROR, SyncStatus.PAUSED, True),
    TransitionCase("paused_to_inactive", SyncStatus.PAUSED, SyncStatus.INACTIVE, False),
    TransitionCase("inactive_to_paused", SyncStatus.INACTIVE, SyncStatus.PAUSED, False),
    TransitionCase("active_to_error", SyncStatus.ACTIVE, SyncStatus.ERROR, False),
]


@pytest.mark.parametrize("case", TRANSITION_CASES, ids=lambda c: c.name)
def test_validate_transition(case: TransitionCase):
    if case.valid:
        SyncStateMachine._validate_transition(case.current, case.target, SYNC_ID)
    else:
        with pytest.raises(InvalidSyncTransitionError) as exc_info:
            SyncStateMachine._validate_transition(case.current, case.target, SYNC_ID)
        assert exc_info.value.current == case.current
        assert exc_info.value.target == case.target
        assert exc_info.value.sync_id == SYNC_ID


def test_validate_transition_without_sync_id():
    """InvalidSyncTransitionError works without sync_id."""
    with pytest.raises(InvalidSyncTransitionError) as exc_info:
        SyncStateMachine._validate_transition(
            SyncStatus.PAUSED, SyncStatus.INACTIVE
        )
    assert exc_info.value.sync_id is None
    assert "paused" in str(exc_info.value)
    assert "inactive" in str(exc_info.value)


# ---------------------------------------------------------------------------
# transition() — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_active_to_paused():
    """Successful transition writes DB and pauses schedules."""
    sync_repo = AsyncMock()
    sync_obj = _make_sync_obj(SyncStatus.ACTIVE)
    sync_repo.get_without_connections = AsyncMock(return_value=sync_obj)

    schedule_svc = AsyncMock()

    sm = _build_sm(sync_repo=sync_repo, schedule_svc=schedule_svc)

    mock_db = AsyncMock()
    with patch(
        "airweave.domains.syncs.sync_state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await sm.transition(SYNC_ID, SyncStatus.PAUSED, _make_ctx(), reason="cred error")

    assert result == SyncTransitionResult(
        applied=True, previous=SyncStatus.ACTIVE, current=SyncStatus.PAUSED
    )
    assert sync_obj.status == SyncStatus.PAUSED
    mock_db.commit.assert_awaited_once()
    schedule_svc.pause_schedules_for_sync.assert_awaited_once_with(
        SYNC_ID, reason="cred error"
    )


@pytest.mark.asyncio
async def test_transition_paused_to_active_unpauses():
    """PAUSED → ACTIVE triggers unpause_schedules_for_sync."""
    sync_repo = AsyncMock()
    sync_obj = _make_sync_obj(SyncStatus.PAUSED)
    sync_repo.get_without_connections = AsyncMock(return_value=sync_obj)

    schedule_svc = AsyncMock()

    sm = _build_sm(sync_repo=sync_repo, schedule_svc=schedule_svc)

    mock_db = AsyncMock()
    with patch(
        "airweave.domains.syncs.sync_state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await sm.transition(SYNC_ID, SyncStatus.ACTIVE, _make_ctx())

    assert result.applied is True
    assert result.previous == SyncStatus.PAUSED
    assert result.current == SyncStatus.ACTIVE
    schedule_svc.unpause_schedules_for_sync.assert_awaited_once_with(SYNC_ID)


# ---------------------------------------------------------------------------
# transition() — idempotent skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_idempotent_skip():
    """Re-writing the current status returns applied=False, no DB write."""
    sync_repo = AsyncMock()
    sync_obj = _make_sync_obj(SyncStatus.ACTIVE)
    sync_repo.get_without_connections = AsyncMock(return_value=sync_obj)

    schedule_svc = AsyncMock()

    sm = _build_sm(sync_repo=sync_repo, schedule_svc=schedule_svc)

    mock_db = AsyncMock()
    with patch(
        "airweave.domains.syncs.sync_state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await sm.transition(SYNC_ID, SyncStatus.ACTIVE, _make_ctx())

    assert result == SyncTransitionResult(
        applied=False, previous=SyncStatus.ACTIVE, current=SyncStatus.ACTIVE
    )
    mock_db.commit.assert_not_awaited()
    schedule_svc.pause_schedules_for_sync.assert_not_awaited()
    schedule_svc.unpause_schedules_for_sync.assert_not_awaited()


# ---------------------------------------------------------------------------
# transition() — sync not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_sync_not_found():
    """ValueError raised when sync doesn't exist."""
    sync_repo = AsyncMock()
    sync_repo.get_without_connections = AsyncMock(return_value=None)

    sm = _build_sm(sync_repo=sync_repo)

    with patch(
        "airweave.domains.syncs.sync_state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(ValueError, match="not found"):
            await sm.transition(SYNC_ID, SyncStatus.PAUSED, _make_ctx())


# ---------------------------------------------------------------------------
# transition() — invalid transition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_invalid_raises():
    """Invalid transition raises InvalidSyncTransitionError."""
    sync_repo = AsyncMock()
    sync_obj = _make_sync_obj(SyncStatus.PAUSED)
    sync_repo.get_without_connections = AsyncMock(return_value=sync_obj)

    sm = _build_sm(sync_repo=sync_repo)

    mock_db = AsyncMock()
    with patch(
        "airweave.domains.syncs.sync_state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(InvalidSyncTransitionError):
            await sm.transition(SYNC_ID, SyncStatus.INACTIVE, _make_ctx())

    mock_db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# Side effect failure is non-fatal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_side_effect_failure_is_non_fatal():
    """Schedule service failure is logged but doesn't raise."""
    sync_repo = AsyncMock()
    sync_obj = _make_sync_obj(SyncStatus.ACTIVE)
    sync_repo.get_without_connections = AsyncMock(return_value=sync_obj)

    schedule_svc = AsyncMock()
    schedule_svc.pause_schedules_for_sync = AsyncMock(side_effect=RuntimeError("RPC down"))

    sm = _build_sm(sync_repo=sync_repo, schedule_svc=schedule_svc)

    mock_db = AsyncMock()
    with patch(
        "airweave.domains.syncs.sync_state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await sm.transition(SYNC_ID, SyncStatus.PAUSED, _make_ctx())

    assert result.applied is True
    mock_db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# _apply_side_effects — default reason
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pause_uses_default_reason():
    """When no reason given, default 'Sync paused' is used."""
    sync_repo = AsyncMock()
    sync_obj = _make_sync_obj(SyncStatus.ACTIVE)
    sync_repo.get_without_connections = AsyncMock(return_value=sync_obj)

    schedule_svc = AsyncMock()

    sm = _build_sm(sync_repo=sync_repo, schedule_svc=schedule_svc)

    mock_db = AsyncMock()
    with patch(
        "airweave.domains.syncs.sync_state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        await sm.transition(SYNC_ID, SyncStatus.PAUSED, _make_ctx())

    schedule_svc.pause_schedules_for_sync.assert_awaited_once_with(
        SYNC_ID, reason="Sync paused"
    )


# ---------------------------------------------------------------------------
# Transitions to non-pause/active states have no schedule side effects
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_to_inactive_no_schedule_side_effects():
    """ACTIVE → INACTIVE doesn't pause or unpause schedules."""
    sync_repo = AsyncMock()
    sync_obj = _make_sync_obj(SyncStatus.ACTIVE)
    sync_repo.get_without_connections = AsyncMock(return_value=sync_obj)

    schedule_svc = AsyncMock()

    sm = _build_sm(sync_repo=sync_repo, schedule_svc=schedule_svc)

    mock_db = AsyncMock()
    with patch(
        "airweave.domains.syncs.sync_state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await sm.transition(SYNC_ID, SyncStatus.INACTIVE, _make_ctx())

    assert result.applied is True
    schedule_svc.pause_schedules_for_sync.assert_not_awaited()
    schedule_svc.unpause_schedules_for_sync.assert_not_awaited()


# ---------------------------------------------------------------------------
# pause_reason persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pause_sets_pause_reason():
    """Transitioning to PAUSED with pause_reason persists it on the sync object."""
    sync_repo = AsyncMock()
    sync_obj = _make_sync_obj(SyncStatus.ACTIVE)
    sync_repo.get_without_connections = AsyncMock(return_value=sync_obj)

    sm = _build_sm(sync_repo=sync_repo)

    mock_db = AsyncMock()
    with patch(
        "airweave.domains.syncs.sync_state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        await sm.transition(
            SYNC_ID,
            SyncStatus.PAUSED,
            _make_ctx(),
            reason="usage limit",
            pause_reason=SyncPauseReason.USAGE_EXHAUSTED,
        )

    assert sync_obj.pause_reason == SyncPauseReason.USAGE_EXHAUSTED.value


@pytest.mark.asyncio
async def test_unpause_clears_pause_reason():
    """Transitioning to ACTIVE clears pause_reason."""
    sync_repo = AsyncMock()
    sync_obj = _make_sync_obj(SyncStatus.PAUSED)
    sync_obj.pause_reason = SyncPauseReason.USAGE_EXHAUSTED.value
    sync_repo.get_without_connections = AsyncMock(return_value=sync_obj)

    sm = _build_sm(sync_repo=sync_repo)

    mock_db = AsyncMock()
    with patch(
        "airweave.domains.syncs.sync_state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        await sm.transition(SYNC_ID, SyncStatus.ACTIVE, _make_ctx())

    assert sync_obj.pause_reason is None


@pytest.mark.asyncio
async def test_pause_without_reason_sets_none():
    """Transitioning to PAUSED without pause_reason sets None (backwards compat)."""
    sync_repo = AsyncMock()
    sync_obj = _make_sync_obj(SyncStatus.ACTIVE)
    sync_repo.get_without_connections = AsyncMock(return_value=sync_obj)

    sm = _build_sm(sync_repo=sync_repo)

    mock_db = AsyncMock()
    with patch(
        "airweave.domains.syncs.sync_state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        await sm.transition(SYNC_ID, SyncStatus.PAUSED, _make_ctx(), reason="manual")

    assert sync_obj.pause_reason is None
