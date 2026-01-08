"""Scope context for entity operations."""

from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class ScopeContext:
    """Defines the scope for entity operations.

    Used by handlers to know which sync/collection/org they're operating in.
    Named "Scope" to avoid clash with user/org identity contexts.

    Attributes:
        sync_id: The sync configuration ID
        collection_id: The target collection ID
        organization_id: The owning organization ID
        source_connection_id: The user-facing source connection ID
        job_id: Optional job ID (None for non-job operations like cleanup)
    """

    sync_id: UUID
    collection_id: UUID
    organization_id: UUID
    source_connection_id: UUID
    job_id: Optional[UUID] = None

    def __repr__(self) -> str:
        """Compact representation for logging."""
        job_part = f", job={self.job_id}" if self.job_id else ""
        return f"ScopeContext(sync={self.sync_id}{job_part})"
