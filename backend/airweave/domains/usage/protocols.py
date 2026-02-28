"""Usage domain protocols — split into read (checker) and write (ledger) concerns.

UsageLimitChecker: Singleton that checks limits given an org_id per call.
UsageLedger: Singleton that accumulates and flushes usage.
"""

from typing import Optional, Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.domains.usage.types import ActionType


@runtime_checkable
class UsageLimitCheckerProtocol(Protocol):
    """Singleton, read-only usage limit enforcement.

    Checks billing status and current usage against plan limits.
    Maintains a short-lived internal cache keyed by org_id.
    """

    async def is_allowed(
        self,
        db: AsyncSession,
        organization_id: UUID,
        action_type: ActionType,
        amount: int = 1,
    ) -> bool:
        """Check whether *amount* units of *action_type* are allowed.

        Returns True if allowed; raises UsageLimitExceededError or
        PaymentRequiredError if not.
        """
        ...


@runtime_checkable
class UsageLedgerProtocol(Protocol):
    """Singleton that accumulates billable usage and flushes to DB.

    Owns its own DB sessions internally — callers never pass a session.
    One instance in the container, shared across all subscribers and sync runs.
    """

    async def record(self, organization_id: UUID, action_type: ActionType, amount: int = 1) -> None:
        """Accumulate a billable action. May flush internally on threshold."""
        ...

    async def flush(self, organization_id: Optional[UUID] = None) -> None:
        """Force-flush pending records to DB. None = flush all orgs."""
        ...
