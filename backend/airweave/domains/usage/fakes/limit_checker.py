"""Fake usage limit checker for testing.

Always allows actions unless explicitly configured to deny.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.domains.usage.protocols import UsageLimitCheckerProtocol
from airweave.domains.usage.types import ActionType


class FakeUsageLimitChecker(UsageLimitCheckerProtocol):
    """Test implementation of UsageLimitCheckerProtocol.

    By default every check returns True (allowed).
    Call ``deny(org_id, action_type)`` to make specific checks return False.

    Usage:
        checker = FakeUsageLimitChecker()
        checker.deny(org_id, ActionType.ENTITIES)

        allowed = await checker.is_allowed(db, org_id, ActionType.ENTITIES)
        assert not allowed
    """

    def __init__(self) -> None:
        """Initialize with empty deny set and call log."""
        self._denied: set[tuple[UUID, ActionType]] = set()
        self.calls: list[tuple[UUID, ActionType, int]] = []

    def deny(self, organization_id: UUID, action_type: ActionType) -> None:
        """Configure a specific (org, action) pair to be denied."""
        self._denied.add((organization_id, action_type))

    def allow_all(self) -> None:
        """Reset to default allow-all behaviour."""
        self._denied.clear()

    async def is_allowed(
        self,
        db: AsyncSession,
        organization_id: UUID,
        action_type: ActionType,
        amount: int = 1,
    ) -> bool:
        """Return True unless the (org, action) pair was explicitly denied."""
        self.calls.append((organization_id, action_type, amount))
        return (organization_id, action_type) not in self._denied
