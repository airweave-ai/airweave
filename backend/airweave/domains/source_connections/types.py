"""Value types for the source_connections domain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, TypedDict
from uuid import UUID

from airweave.core.shared_models import SourceConnectionErrorCategory, SyncJobStatus, SyncStatus


@dataclass(frozen=True, slots=True)
class ErrorClassification:
    """Result of classify_error(): category and human-readable message."""

    category: Optional[SourceConnectionErrorCategory] = None
    message: Optional[str] = None


class ScheduleInfo(TypedDict):
    """Typed return value from get_schedule_info (replaces Dict[str, Any])."""

    cron_expression: Optional[str]
    is_continuous: bool
    cursor_field: Optional[str]
    cursor_value: Optional[str]


@dataclass(frozen=True, slots=True)
class LastJobInfo:
    """Last sync job summary from get_multi_with_stats."""

    status: SyncJobStatus
    completed_at: Optional[datetime]
    error_category: Optional[str] = None


@dataclass(frozen=True, slots=True)
class SourceConnectionStats:
    """Typed intermediate between get_multi_with_stats and build_list_item.

    Every field matches the dict contract produced by
    crud.source_connection.get_multi_with_stats (lines 106-125).
    """

    id: UUID
    name: str
    short_name: str
    readable_collection_id: str
    created_at: datetime
    modified_at: datetime
    is_authenticated: bool
    readable_auth_provider_id: Optional[str]
    connection_init_session_id: Optional[UUID]
    is_active: bool
    authentication_method: Optional[str]
    last_job: Optional[LastJobInfo]
    entity_count: int
    federated_search: bool
    sync_status: Optional[SyncStatus] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SourceConnectionStats:
        """Construct from the raw dict returned by get_multi_with_stats.

        Fails loudly if required keys are missing.
        """
        raw_job = data["last_job"]
        last_job = (
            LastJobInfo(
                status=raw_job["status"],
                completed_at=raw_job.get("completed_at"),
                error_category=raw_job.get("error_category"),
            )
            if raw_job
            else None
        )

        raw_sync_status = data.get("sync_status")
        sync_status = (
            SyncStatus(raw_sync_status)
            if raw_sync_status is not None and not isinstance(raw_sync_status, SyncStatus)
            else raw_sync_status
        )

        return cls(
            id=data["id"],
            name=data["name"],
            short_name=data["short_name"],
            readable_collection_id=data["readable_collection_id"],
            created_at=data["created_at"],
            modified_at=data["modified_at"],
            is_authenticated=data["is_authenticated"],
            readable_auth_provider_id=data["readable_auth_provider_id"],
            connection_init_session_id=data["connection_init_session_id"],
            is_active=data["is_active"],
            authentication_method=data["authentication_method"],
            last_job=last_job,
            entity_count=data["entity_count"],
            federated_search=data["federated_search"],
            sync_status=sync_status,
        )
