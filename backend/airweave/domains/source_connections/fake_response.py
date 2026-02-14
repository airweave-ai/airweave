"""Fake response builder for testing."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from airweave.core.shared_models import SourceConnectionStatus, SyncJobStatus
from airweave.schemas.source_connection import (
    AuthenticationDetails,
    AuthenticationMethod,
    SourceConnection,
    SourceConnectionJob,
    SourceConnectionListItem,
)


class FakeResponseBuilder:
    """Fake implementation of ResponseBuilderProtocol.

    Returns canned responses built from the source_conn attributes.
    Set should_raise for error paths.
    """

    def __init__(self, should_raise: Optional[Exception] = None) -> None:
        """Initialize with optional error injection."""
        self._should_raise = should_raise

    async def build_response(self, db: Any, source_conn: Any, ctx: Any) -> SourceConnection:
        """Build a minimal SourceConnection from source_conn attributes."""
        if self._should_raise:
            raise self._should_raise

        now = datetime.now(timezone.utc)
        return SourceConnection(
            id=getattr(source_conn, "id", uuid4()),
            organization_id=getattr(source_conn, "organization_id", uuid4()),
            name=getattr(source_conn, "name", "Test Connection"),
            description=getattr(source_conn, "description", None),
            short_name=getattr(source_conn, "short_name", "test"),
            readable_collection_id=getattr(source_conn, "readable_collection_id", "col-123"),
            status=SourceConnectionStatus.ACTIVE,
            created_at=getattr(source_conn, "created_at", now),
            modified_at=getattr(source_conn, "modified_at", now),
            auth=AuthenticationDetails(
                method=AuthenticationMethod.DIRECT,
                authenticated=getattr(source_conn, "is_authenticated", True),
            ),
        )

    def build_list_item(self, data: Dict[str, Any]) -> SourceConnectionListItem:
        """Build a minimal SourceConnectionListItem."""
        if self._should_raise:
            raise self._should_raise

        return SourceConnectionListItem(
            id=data.get("id", uuid4()),
            name=data.get("name", ""),
            short_name=data.get("short_name", ""),
            readable_collection_id=data.get("readable_collection_id", ""),
            status=SourceConnectionStatus.ACTIVE,
            is_authenticated=data.get("is_authenticated", True),
            entity_count=data.get("entity_count", 0),
            federated_search=data.get("federated_search", False),
        )

    def map_sync_job(self, job: Any, source_connection_id: UUID) -> SourceConnectionJob:
        """Build a minimal SourceConnectionJob."""
        if self._should_raise:
            raise self._should_raise

        return SourceConnectionJob(
            id=getattr(job, "id", uuid4()),
            source_connection_id=source_connection_id,
            status=getattr(job, "status", SyncJobStatus.COMPLETED),
            started_at=getattr(job, "started_at", None),
            completed_at=getattr(job, "completed_at", None),
            duration_seconds=None,
            entities_inserted=0,
            entities_updated=0,
            entities_deleted=0,
            entities_failed=0,
            error=None,
        )

    def set_should_raise(self, exc: Optional[Exception]) -> None:
        """Configure error injection."""
        self._should_raise = exc
