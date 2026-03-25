"""Value objects for the syncs domain."""

from typing import Optional
from uuid import UUID

from dataclasses import dataclass

from airweave import schemas
from airweave.core.shared_models import SyncStatus

CONTINUOUS_SOURCE_DEFAULT_CRON = "*/5 * * * *"
DAILY_CRON_TEMPLATE = "{minute} {hour} * * *"


class InvalidSyncTransitionError(Exception):
    """Raised when a sync status transition violates the state machine graph."""

    def __init__(
        self,
        current: SyncStatus,
        target: SyncStatus,
        sync_id: UUID | str | None = None,
    ) -> None:
        """Initialize with current/target status and optional sync ID."""
        self.current = current
        self.target = target
        self.sync_id = sync_id
        suffix = f" for sync {sync_id}" if sync_id else ""
        super().__init__(f"Invalid sync transition {current.value} → {target.value}{suffix}")


@dataclass(frozen=True)
class SyncTransitionResult:
    """Outcome of a sync-level transition attempt."""

    applied: bool
    previous: SyncStatus
    current: SyncStatus


@dataclass(frozen=True)
class SyncProvisionResult:
    """Result of provision_sync(): the created sync, optional job, and resolved schedule."""

    sync_id: UUID
    sync: schemas.Sync
    sync_job: Optional[schemas.SyncJob]
    cron_schedule: Optional[str]
