"""Tests for SyncStateMachine — transition validation, idempotency, side effects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from temporalio.service import RPCError

from airweave.core.shared_models import SyncPauseReason, SyncStatus
from airweave.domains.syncs.state_machine import SyncStateMachine
from airweave.domains.syncs.types import (
    InvalidSyncTransitionError,
    OptimisticLockError,
    SyncTransitionResult,
)

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
    repo = sync_repo or AsyncMock()
    if sync_repo is None:
        repo.transition_status = AsyncMock(return_value=None)
    return SyncStateMachine(
        sync_repo=repo,
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
    """Successful transition delegates to repo and pauses schedules."""
    sync_repo = AsyncMock()
    sync_obj = _make_sync_obj(SyncStatus.ACTIVE)
    sync_repo.get_without_connections = AsyncMock(return_value=sync_obj)
    sync_repo.transition_status = AsyncMock()

    schedule_svc = AsyncMock()

    sm = _build_sm(sync_repo=sync_repo, schedule_svc=schedule_svc)

    mock_db = AsyncMock()
    with patch(
        "airweave.domains.syncs.state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await sm.transition(SYNC_ID, SyncStatus.PAUSED, _make_ctx(), reason="cred error")

    assert result == SyncTransitionResult(
        applied=True, previous=SyncStatus.ACTIVE, current=SyncStatus.PAUSED
    )
    sync_repo.transition_status.assert_awaited_once_with(
        mock_db, SYNC_ID, SyncStatus.ACTIVE, SyncStatus.PAUSED
    )
    mock_db.commit.assert_awaited_once()
    schedule_svc.pause_schedules_for_sync.assert_awaited_once_with(
        SYNC_ID, reason="cred error"
    )


@pytest.mark.asyncio
async def test_transition_paused_to_active_unpauses():
    """PAUSED -> ACTIVE triggers unpause_schedules_for_sync."""
    sync_repo = AsyncMock()
    sync_obj = _make_sync_obj(SyncStatus.PAUSED)
    sync_repo.get_without_connections = AsyncMock(return_value=sync_obj)
    sync_repo.transition_status = AsyncMock()

    schedule_svc = AsyncMock()

    sm = _build_sm(sync_repo=sync_repo, schedule_svc=schedule_svc)

    mock_db = AsyncMock()
    with patch(
        "airweave.domains.syncs.state_machine.get_db_context"
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
        "airweave.domains.syncs.state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await sm.transition(SYNC_ID, SyncStatus.ACTIVE, _make_ctx())

    assert result == SyncTransitionResult(
        applied=False, previous=SyncStatus.ACTIVE, current=SyncStatus.ACTIVE
    )
    sync_repo.transition_status.assert_not_awaited()
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
        "airweave.domains.syncs.state_machine.get_db_context"
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
        "airweave.domains.syncs.state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(InvalidSyncTransitionError):
            await sm.transition(SYNC_ID, SyncStatus.INACTIVE, _make_ctx())

    sync_repo.transition_status.assert_not_awaited()
    mock_db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# Side effect failure (RPCError/OSError) is non-fatal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_side_effect_rpc_error_is_non_fatal():
    """RPCError from Temporal is logged but doesn't raise."""
    sync_repo = AsyncMock()
    sync_obj = _make_sync_obj(SyncStatus.ACTIVE)
    sync_repo.get_without_connections = AsyncMock(return_value=sync_obj)
    sync_repo.transition_status = AsyncMock()

    schedule_svc = AsyncMock()
    schedule_svc.pause_schedules_for_sync = AsyncMock(
        side_effect=OSError("connection refused")
    )

    sm = _build_sm(sync_repo=sync_repo, schedule_svc=schedule_svc)

    mock_db = AsyncMock()
    with patch(
        "airweave.domains.syncs.state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await sm.transition(SYNC_ID, SyncStatus.PAUSED, _make_ctx())

    assert result.applied is True
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_side_effect_unexpected_error_propagates():
    """Non-network errors from schedule service are NOT swallowed."""
    sync_repo = AsyncMock()
    sync_obj = _make_sync_obj(SyncStatus.ACTIVE)
    sync_repo.get_without_connections = AsyncMock(return_value=sync_obj)
    sync_repo.transition_status = AsyncMock()

    schedule_svc = AsyncMock()
    schedule_svc.pause_schedules_for_sync = AsyncMock(
        side_effect=RuntimeError("programming bug")
    )

    sm = _build_sm(sync_repo=sync_repo, schedule_svc=schedule_svc)

    mock_db = AsyncMock()
    with patch(
        "airweave.domains.syncs.state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(RuntimeError, match="programming bug"):
            await sm.transition(SYNC_ID, SyncStatus.PAUSED, _make_ctx())


# ---------------------------------------------------------------------------
# _apply_side_effects — default reason
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pause_uses_default_reason():
    """When no reason given, default 'Sync paused' is used."""
    sync_repo = AsyncMock()
    sync_obj = _make_sync_obj(SyncStatus.ACTIVE)
    sync_repo.get_without_connections = AsyncMock(return_value=sync_obj)
    sync_repo.transition_status = AsyncMock()

    schedule_svc = AsyncMock()

    sm = _build_sm(sync_repo=sync_repo, schedule_svc=schedule_svc)

    mock_db = AsyncMock()
    with patch(
        "airweave.domains.syncs.state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        await sm.transition(SYNC_ID, SyncStatus.PAUSED, _make_ctx())

    schedule_svc.pause_schedules_for_sync.assert_awaited_once_with(
        SYNC_ID, reason="Sync paused"
    )


# ---------------------------------------------------------------------------
# ACTIVE -> INACTIVE pauses schedules to prevent orphaned schedule accumulation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_to_inactive_pauses_schedules():
    """ACTIVE -> INACTIVE pauses schedules with deactivation reason."""
    sync_repo = AsyncMock()
    sync_obj = _make_sync_obj(SyncStatus.ACTIVE)
    sync_repo.get_without_connections = AsyncMock(return_value=sync_obj)
    sync_repo.transition_status = AsyncMock()

    schedule_svc = AsyncMock()

    sm = _build_sm(sync_repo=sync_repo, schedule_svc=schedule_svc)

    mock_db = AsyncMock()
    with patch(
        "airweave.domains.syncs.state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await sm.transition(SYNC_ID, SyncStatus.INACTIVE, _make_ctx())

    assert result.applied is True
    schedule_svc.pause_schedules_for_sync.assert_awaited_once_with(
        SYNC_ID, reason="Sync deactivated"
    )
    schedule_svc.unpause_schedules_for_sync.assert_not_awaited()


# ---------------------------------------------------------------------------
# Optimistic locking — concurrent modification detected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transition_optimistic_lock_failure():
    """OptimisticLockError raised when repo detects concurrent modification."""
    sync_repo = AsyncMock()
    sync_obj = _make_sync_obj(SyncStatus.ACTIVE)
    sync_repo.get_without_connections = AsyncMock(return_value=sync_obj)
    sync_repo.transition_status = AsyncMock(
        side_effect=OptimisticLockError(SYNC_ID, SyncStatus.ACTIVE)
    )

    sm = _build_sm(sync_repo=sync_repo)

    mock_db = AsyncMock()
    with patch(
        "airweave.domains.syncs.state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(OptimisticLockError) as exc_info:
            await sm.transition(SYNC_ID, SyncStatus.PAUSED, _make_ctx())

    assert exc_info.value.sync_id == SYNC_ID
    assert exc_info.value.expected == SyncStatus.ACTIVE
    mock_db.commit.assert_not_awaited()


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
        "airweave.domains.syncs.state_machine.get_db_context"
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
        "airweave.domains.syncs.state_machine.get_db_context"
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
        "airweave.domains.syncs.state_machine.get_db_context"
    ) as mock_ctx:
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        await sm.transition(SYNC_ID, SyncStatus.PAUSED, _make_ctx(), reason="manual")

    assert sync_obj.pause_reason is None


# ---------------------------------------------------------------------------
# SyncStatus enum deserialization — DB string → enum roundtrip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("member", list(SyncStatus), ids=lambda m: m.value)
def test_sync_status_from_string_value(member: SyncStatus):
    """Every SyncStatus member roundtrips from its DB string representation."""
    assert SyncStatus(member.value) is member


@pytest.mark.parametrize("member", list(SyncStatus), ids=lambda m: m.value)
def test_sync_status_string_equality(member: SyncStatus):
    """SyncStatus members compare equal to their string value (str enum)."""
    assert member == member.value
    assert member.value == member


def test_sync_status_rejects_unknown_value():
    """Unknown string raises ValueError — guards against DB/enum drift."""
    with pytest.raises(ValueError):
        SyncStatus("deleted")


@pytest.mark.parametrize("member", list(SyncStatus), ids=lambda m: m.value)
def test_sync_status_pydantic_coercion(member: SyncStatus):
    """Pydantic schema correctly coerces a raw string to SyncStatus."""
    from airweave.schemas.sync import SyncWithoutConnections

    data = SyncWithoutConnections.model_validate(
        {
            "name": "test",
            "status": member.value,
            "id": str(SYNC_ID),
            "organization_id": str(ORG_ID),
            "created_at": "2025-01-01T00:00:00",
            "modified_at": "2025-01-01T00:00:00",
        }
    )
    assert data.status is member
    assert isinstance(data.status, SyncStatus)
