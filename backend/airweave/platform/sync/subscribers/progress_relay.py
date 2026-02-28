"""Progress relay — pure subscriber combining three event streams.

Subscribes to ``entity.*``, ``access_control.*``, and ``sync.*`` on
the global EventBus. Translates domain events into PubSub messages
for SSE endpoints. Zero direct method calls from the sync pipeline.

- sync.running → session auto-created
- entity.batch_processed → throttled progress snapshots
- access_control.batch_processed → progress snapshot during ACL membership sync
- sync.completed/failed/cancelled → final state + session cleanup

No registration needed — sessions are created automatically when
a sync.running event arrives.
"""

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID

from airweave.core.events.base import DomainEvent
from airweave.core.events.enums import SyncEventType
from airweave.core.events.sync import (
    AccessControlMembershipBatchProcessedEvent,
    EntityBatchProcessedEvent,
    SyncLifecycleEvent,
    TypeActionCounts,
)
from airweave.core.protocols.event_bus import EventSubscriber
from airweave.core.protocols.pubsub import PubSub
from airweave.core.shared_models import SyncJobStatus
from airweave.schemas.sync_pubsub import (
    EntityStateUpdate,
    SyncCompleteMessage,
    SyncProgressUpdate,
)

logger = logging.getLogger(__name__)

_SESSION_TTL_SECONDS = 300

_TERMINAL_SYNC_EVENTS = {
    SyncEventType.COMPLETED,
    SyncEventType.FAILED,
    SyncEventType.CANCELLED,
}

_STATUS_MAP = {
    SyncEventType.COMPLETED: SyncJobStatus.COMPLETED,
    SyncEventType.FAILED: SyncJobStatus.FAILED,
    SyncEventType.CANCELLED: SyncJobStatus.CANCELLED,
}


@dataclass
class _RelaySession:
    """Per-sync session — self-accumulating from events, no tracker needed."""

    job_id: UUID
    sync_id: UUID

    # Accumulated from EntityBatchProcessedEvent deltas
    inserted: int = 0
    updated: int = 0
    deleted: int = 0
    kept: int = 0
    skipped: int = 0
    type_counts: Dict[str, TypeActionCounts] = field(default_factory=dict)

    # Throttling
    publish_threshold: int = 3
    ops_since_publish: int = field(default=0, init=False)
    total_ops: int = field(default=0, init=False)
    last_status_update_ops: int = field(default=0, init=False)
    status_update_interval: int = field(default=50, init=False)
    start_time: float = field(default_factory=time.monotonic)

    # Lifecycle
    finished_at: Optional[float] = field(default=None, init=False)

    @property
    def is_finished(self) -> bool:
        return self.finished_at is not None

    @property
    def is_expired(self) -> bool:
        return self.finished_at is not None and (
            time.monotonic() - self.finished_at > _SESSION_TTL_SECONDS
        )

    def apply_batch(self, event: EntityBatchProcessedEvent) -> None:
        """Accumulate deltas from a batch event."""
        self.inserted += event.inserted
        self.updated += event.updated
        self.deleted += event.deleted
        self.kept += event.kept

        for type_name, counts in event.type_breakdown.items():
            existing = self.type_counts.get(type_name)
            if existing is None:
                self.type_counts[type_name] = counts
            else:
                self.type_counts[type_name] = TypeActionCounts(
                    inserted=existing.inserted + counts.inserted,
                    updated=existing.updated + counts.updated,
                    deleted=existing.deleted + counts.deleted,
                    kept=existing.kept + counts.kept,
                )

    @property
    def total_entities(self) -> int:
        return self.inserted + self.updated

    @property
    def named_counts(self) -> Dict[str, int]:
        """Per-type total counts (inserts + updates) for this sync."""
        result: Dict[str, int] = defaultdict(int)
        for type_name, counts in self.type_counts.items():
            result[type_name] = counts.inserted + counts.updated + counts.kept
        return dict(result)


class SyncProgressRelay(EventSubscriber):
    """Combines entity batch, ACL membership, and sync lifecycle event streams.

    Sessions are auto-created on ``sync.running`` events.
    No registration or factory wiring needed.
    """

    EVENT_PATTERNS = [
        "entity.*",
        "access_control.*",
        "sync.running",
        "sync.completed",
        "sync.failed",
        "sync.cancelled",
    ]

    def __init__(self, pubsub: PubSub) -> None:
        """Initialize with a PubSub transport for publishing progress."""
        self._pubsub = pubsub
        self._sessions: dict[UUID, _RelaySession] = {}

    @property
    def active_session_count(self) -> int:
        """Return the number of relay sessions that have not finished."""
        return sum(1 for s in self._sessions.values() if not s.is_finished)

    # ------------------------------------------------------------------
    # EventBus handler
    # ------------------------------------------------------------------

    async def handle(self, event: DomainEvent) -> None:
        """Dispatch a domain event to the appropriate handler."""
        if isinstance(event, EntityBatchProcessedEvent):
            await self._handle_batch(event)
        elif isinstance(event, AccessControlMembershipBatchProcessedEvent):
            await self._handle_acl_batch(event)
        elif isinstance(event, SyncLifecycleEvent):
            if event.event_type == SyncEventType.RUNNING:
                self._handle_running(event)
            elif event.event_type in _TERMINAL_SYNC_EVENTS:
                await self._handle_terminal(event)

    def _handle_running(self, event: SyncLifecycleEvent) -> None:
        """Auto-create session when a sync starts running."""
        self._reap_expired()
        self._sessions[event.sync_job_id] = _RelaySession(
            job_id=event.sync_job_id,
            sync_id=event.sync_id,
        )

    async def _handle_batch(self, event: EntityBatchProcessedEvent) -> None:
        session = self._sessions.get(event.sync_job_id)
        if session is None or session.is_finished:
            return

        session.apply_batch(event)

        batch_ops = event.inserted + event.updated + event.deleted + event.kept
        session.ops_since_publish += batch_ops
        session.total_ops += batch_ops

        if session.ops_since_publish >= session.publish_threshold:
            await self._publish_progress(session)
            session.ops_since_publish = 0

        if session.total_ops - session.last_status_update_ops >= session.status_update_interval:
            self._log_status_update(session)
            session.last_status_update_ops = session.total_ops

    async def _handle_acl_batch(self, event: AccessControlMembershipBatchProcessedEvent) -> None:
        session = self._sessions.get(event.sync_job_id)
        if session is None or session.is_finished:
            return
        await self._publish_progress(session)

    async def _handle_terminal(self, event: SyncLifecycleEvent) -> None:
        session = self._sessions.get(event.sync_job_id)
        if session is None:
            return

        status = _STATUS_MAP.get(event.event_type, SyncJobStatus.COMPLETED)
        error = event.error if hasattr(event, "error") else None

        await self._publish_completion(session, status, error)
        session.finished_at = time.monotonic()

    # ------------------------------------------------------------------
    # Internal publishing
    # ------------------------------------------------------------------

    async def _publish_progress(self, session: _RelaySession) -> None:
        update = SyncProgressUpdate(
            inserted=session.inserted,
            updated=session.updated,
            deleted=session.deleted,
            kept=session.kept,
            skipped=session.skipped,
            last_update_timestamp=datetime.now(timezone.utc).isoformat(),
        )

        data = update.model_dump()
        await self._pubsub.publish("sync_job", session.job_id, data)

        snapshot_key = f"sync_progress_snapshot:{session.job_id}"
        await self._pubsub.store_snapshot(snapshot_key, json.dumps(data), ttl_seconds=1800)

        await self._publish_state(session)

    async def _publish_state(self, session: _RelaySession) -> None:
        state = EntityStateUpdate(
            job_id=session.job_id,
            sync_id=session.sync_id,
            entity_counts=session.named_counts,
            total_entities=session.total_entities,
            job_status=SyncJobStatus.RUNNING,
        )

        try:
            await self._pubsub.publish("sync_job_state", session.job_id, state.model_dump_json())
        except Exception as e:
            logger.error(f"Failed to publish entity state for {session.job_id}: {e}")

    async def _publish_completion(
        self, session: _RelaySession, status: SyncJobStatus, error: Optional[str] = None
    ) -> None:
        update = SyncProgressUpdate(
            inserted=session.inserted,
            updated=session.updated,
            deleted=session.deleted,
            kept=session.kept,
            skipped=session.skipped,
            status=status,
            last_update_timestamp=datetime.now(timezone.utc).isoformat(),
        )
        await self._pubsub.publish("sync_job", session.job_id, update.model_dump())

        is_complete = status == SyncJobStatus.COMPLETED
        is_failed = status == SyncJobStatus.FAILED
        error_msg = error if error else ("Sync failed" if is_failed else None)

        completion_msg = SyncCompleteMessage(
            job_id=session.job_id,
            sync_id=session.sync_id,
            is_complete=is_complete,
            is_failed=is_failed,
            final_counts=session.named_counts,
            total_entities=session.total_entities,
            total_operations=session.total_ops,
            final_status=status,
            error=error_msg,
        )

        try:
            await self._pubsub.publish(
                "sync_job_state", session.job_id, completion_msg.model_dump_json()
            )
        except Exception as e:
            logger.error(f"Failed to publish completion for {session.job_id}: {e}")

        self._log_final_summary(session, status)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _reap_expired(self) -> None:
        expired = [jid for jid, s in self._sessions.items() if s.is_expired]
        for jid in expired:
            self._sessions.pop(jid, None)
        if expired:
            logger.debug(f"Reaped {len(expired)} expired relay sessions")

    @staticmethod
    def _log_status_update(session: _RelaySession) -> None:
        elapsed = time.monotonic() - session.start_time
        rate = session.total_ops / elapsed if elapsed > 0 else 0
        logger.info(
            f"[{session.job_id}] Progress: {session.total_ops} ops ({rate:.1f}/s) | "
            f"Ins: {session.inserted} Upd: {session.updated} Del: {session.deleted} "
            f"Kep: {session.kept} Skp: {session.skipped}"
        )

    @staticmethod
    def _log_final_summary(session: _RelaySession, status: SyncJobStatus) -> None:
        text = {
            SyncJobStatus.COMPLETED: "completed",
            SyncJobStatus.CANCELLED: "cancelled",
            SyncJobStatus.FAILED: "failed",
        }.get(status, status.value)

        ops_summary = (
            f"I:{session.inserted} U:{session.updated} D:{session.deleted} "
            f"K:{session.kept} S:{session.skipped}"
        )
        logger.info(
            f"[{session.job_id}] Sync {text} | "
            f"Total entities: {session.total_entities} | "
            f"Ops: {session.total_ops} ({ops_summary})"
        )
