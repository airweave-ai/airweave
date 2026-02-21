"""Value objects for the syncs domain."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID

from airweave import schemas

CONTINUOUS_SOURCE_DEFAULT_CRON = "*/5 * * * *"
DAILY_CRON_TEMPLATE = "{minute} {hour} * * *"


@dataclass(frozen=True)
class SyncProvisionResult:
    """Result of provision_sync(): the created sync, optional job, and resolved schedule."""

    sync_id: UUID
    sync: schemas.Sync
    sync_job: Optional[schemas.SyncJob]
    cron_schedule: Optional[str]


@dataclass
class StatsUpdate:
    """Stat fields extracted from SyncStats for a sync job update."""

    entities_inserted: int = 0
    entities_updated: int = 0
    entities_deleted: int = 0
    entities_kept: int = 0
    entities_skipped: int = 0
    entities_encountered: dict[str, int] = field(default_factory=dict)


@dataclass
class TimestampUpdate:
    """Timestamp / error fields for a sync job update."""

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error: Optional[str] = None
