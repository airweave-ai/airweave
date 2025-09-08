"""Schemas for sync job pubsub messages.

These schemas define the structure of messages sent over Redis pubsub channels
for real-time sync progress and entity state updates.
"""

from datetime import datetime
from typing import Dict, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from airweave.core.shared_models import SyncJobStatus


class SyncProgressUpdate(BaseModel):
    """Sync progress update for differential tracking.

    This tracks incremental changes (inserted, updated, deleted) during sync.
    """

    inserted: int = 0
    updated: int = 0
    deleted: int = 0
    kept: int = 0
    skipped: int = 0
    entities_encountered: Dict[str, int] = Field(
        default_factory=dict, description="Count of entities by type name"
    )
    is_complete: bool = False
    is_failed: bool = False


class EntityStateUpdate(BaseModel):
    """Entity state update for absolute count tracking.

    This provides the total count of entities at a point in time during sync.
    """

    # Use Literal in the type annotation and a plain default; do not pass invalid kwargs to Field
    type: Literal["entity_state"] = "entity_state"
    job_id: UUID = Field(..., description="The sync job ID")
    sync_id: UUID = Field(..., description="The sync ID")
    entity_counts: Dict[str, int] = Field(
        default_factory=dict, description="Total count of entities by type name"
    )
    total_entities: int = Field(0, description="Total count across all entity types")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Include the current job status for frontend state management
    job_status: SyncJobStatus = Field(
        SyncJobStatus.IN_PROGRESS, description="Current status of the sync job"
    )


class SyncCompleteMessage(BaseModel):
    """Sync completion message sent when a sync job finishes.

    This is sent at the end of a sync to indicate final state.
    """

    # Use Literal in the type annotation and a plain default; do not pass invalid kwargs to Field
    type: Literal["sync_complete"] = "sync_complete"
    job_id: UUID = Field(..., description="The sync job ID")
    sync_id: UUID = Field(..., description="The sync ID")
    is_complete: bool = Field(..., description="Whether sync completed successfully")
    is_failed: bool = Field(..., description="Whether sync failed")
    final_counts: Dict[str, int] = Field(
        default_factory=dict, description="Final count of entities by type name"
    )
    total_entities: int = Field(0, description="Final total count")
    total_operations: int = Field(0, description="Total operations performed")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Final job status
    final_status: SyncJobStatus = Field(
        ..., description="Final status of the sync job (COMPLETED or FAILED)"
    )
    error: Optional[str] = Field(None, description="Error message if failed")
