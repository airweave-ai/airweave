"""Usage domain protocols."""

from typing import Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.logging import ContextualLogger
from airweave.domains.usage.types import ActionType


@runtime_checkable
class UsageGuardrailProtocol(Protocol):
    """Per-organization usage tracking and limit enforcement."""

    async def is_allowed(self, db: AsyncSession, action_type: ActionType, amount: int = 1) -> bool:
        """Check whether *amount* units of *action_type* are allowed.

        Returns True if allowed, raises UsageLimitExceededError or
        PaymentRequiredError if not.
        """
        ...

    async def increment(self, db: AsyncSession, action_type: ActionType, amount: int = 1) -> None:
        """Buffer an increment; flushes to DB when threshold is reached."""
        ...

    async def decrement(self, db: AsyncSession, action_type: ActionType, amount: int = 1) -> None:
        """Buffer a decrement; flushes to DB when threshold is reached."""
        ...

    async def flush_all(self, db: AsyncSession) -> None:
        """Flush all pending increments to the database."""
        ...


@runtime_checkable
class UsageServiceFactoryProtocol(Protocol):
    """Factory that creates per-organization UsageGuardrailProtocol instances.

    Lives on the Container as a singleton. The factory holds shared repository
    dependencies; ``create()`` builds a stateful, per-org service instance.
    """

    def create(
        self,
        organization_id: UUID,
        logger: ContextualLogger,
    ) -> UsageGuardrailProtocol:
        """Create a new enforcement service for *organization_id*."""
        ...
