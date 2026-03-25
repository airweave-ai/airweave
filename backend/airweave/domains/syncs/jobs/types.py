"""Value objects for the sync jobs subdomain."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID

from airweave.core.shared_models import SourceConnectionErrorCategory, SyncJobStatus


@dataclass(frozen=True)
class LifecycleData:
    """Identifiers needed to publish a SyncLifecycleEvent."""

    organization_id: UUID
    sync_id: UUID
    sync_job_id: UUID
    collection_id: UUID
    source_connection_id: UUID
    source_type: str = ""
    collection_name: str = ""
    collection_readable_id: str = ""


@dataclass(frozen=True)
class TransitionResult:
    """Outcome of a transition attempt."""

    applied: bool
    previous: SyncJobStatus
    current: SyncJobStatus


class InvalidTransitionError(Exception):
    """Raised when a sync job status transition violates the state machine graph."""

    def __init__(
        self,
        current: SyncJobStatus,
        target: SyncJobStatus,
        sync_job_id: UUID | str | None = None,
    ) -> None:
        """Initialize with current/target status and optional job ID."""
        self.current = current
        self.target = target
        self.sync_job_id = sync_job_id
        job = f" for job {sync_job_id}" if sync_job_id else ""
        super().__init__(f"Invalid transition {current.value} → {target.value}{job}")


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
    error_category: Optional[SourceConnectionErrorCategory] = None
