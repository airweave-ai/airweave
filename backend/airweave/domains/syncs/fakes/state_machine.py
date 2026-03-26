"""Fake sync state machine for testing."""

from uuid import UUID

from airweave.core.context import BaseContext
from airweave.core.shared_models import SyncPauseReason, SyncStatus
from airweave.domains.syncs.protocols import SyncStateMachineProtocol
from airweave.domains.syncs.types import SyncTransitionResult


class FakeSyncStateMachine(SyncStateMachineProtocol):
    """In-memory fake for SyncStateMachineProtocol."""

    def __init__(self) -> None:
        """Initialize with empty state."""
        self._calls: list[tuple] = []
        self._should_raise: Exception | None = None
        self._result: SyncTransitionResult | None = None

    def set_error(self, error: Exception) -> None:
        """Make all subsequent calls raise this error."""
        self._should_raise = error

    def set_result(self, result: SyncTransitionResult) -> None:
        """Configure transition() return value."""
        self._result = result

    async def transition(
        self,
        sync_id: UUID,
        target: SyncStatus,
        ctx: BaseContext,
        *,
        reason: str = "",
        pause_reason: SyncPauseReason | None = None,
    ) -> SyncTransitionResult:
        """Record call and return canned result."""
        self._calls.append(("transition", sync_id, target, ctx, reason, pause_reason))
        if self._should_raise:
            raise self._should_raise
        if self._result is not None:
            return self._result
        return SyncTransitionResult(applied=True, previous=SyncStatus.INACTIVE, current=target)
