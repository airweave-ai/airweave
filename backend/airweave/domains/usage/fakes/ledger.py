"""Fake usage ledger for testing.

Records all calls for assertions without touching the database.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional
from uuid import UUID

from airweave.domains.usage.protocols import UsageLedgerProtocol
from airweave.domains.usage.types import ActionType


class FakeUsageLedger(UsageLedgerProtocol):
    """Test implementation of UsageLedgerProtocol.

    Tracks recorded amounts and flush calls for assertions.

    Usage:
        ledger = FakeUsageLedger()
        await some_subscriber(ledger=ledger)

        assert ledger.recorded[(org_id, ActionType.ENTITIES)] == 42
        assert org_id in ledger.flushed_orgs
    """

    def __init__(self) -> None:
        """Initialize empty recording state."""
        self.recorded: dict[tuple[UUID, ActionType], int] = defaultdict(int)
        self.record_calls: list[tuple[UUID, ActionType, int]] = []
        self.flushed_orgs: list[Optional[UUID]] = []

    async def record(
        self,
        organization_id: UUID,
        action_type: ActionType,
        amount: int = 1,
    ) -> None:
        """Record a usage increment."""
        self.record_calls.append((organization_id, action_type, amount))
        self.recorded[(organization_id, action_type)] += amount

    async def flush(self, organization_id: Optional[UUID] = None) -> None:
        """Record that a flush was requested."""
        self.flushed_orgs.append(organization_id)

    def clear(self) -> None:
        """Reset all recorded state."""
        self.recorded.clear()
        self.record_calls.clear()
        self.flushed_orgs.clear()
