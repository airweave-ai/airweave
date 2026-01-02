"""Sync execution configuration for controlling sync behavior."""

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SyncExecutionConfig(BaseModel):
    """Declarative sync execution configuration.

    Each component reads only the flags it needs - highly modular.
    Config is persisted in sync_job.execution_config_json to avoid Temporal bloat.
    """

    # Destination selection
    target_destinations: Optional[List[UUID]] = Field(
        None, description="If set, ONLY write to these destinations"
    )
    exclude_destinations: Optional[List[UUID]] = Field(
        None, description="Skip these destinations"
    )
    destination_strategy: str = Field(
        "active_and_shadow",
        description="active_only|shadow_only|all|active_and_shadow",
    )

    # Handler toggles
    enable_vector_handlers: bool = Field(True, description="Enable VectorDBHandler")
    enable_raw_data_handler: bool = Field(True, description="Enable RawDataHandler (ARF)")
    enable_postgres_handler: bool = Field(True, description="Enable PostgresMetadataHandler")

    # Behavior flags
    skip_hash_comparison: bool = Field(False, description="Force INSERT for all entities")
    skip_hash_updates: bool = Field(
        False, description="Don't update content_hash column"
    )
    skip_cursor_updates: bool = Field(
        False, description="Don't save cursor progress (for ARF-only syncs)"
    )

    # Performance
    max_workers: int = Field(20, description="Max concurrent workers")
    batch_size: int = Field(100, description="Entity batch size")

    @classmethod
    def default(cls) -> "SyncExecutionConfig":
        """Normal sync to active+shadow destinations."""
        return cls()

    @classmethod
    def arf_capture_only(cls) -> "SyncExecutionConfig":
        """Capture to ARF without vector DBs or hash updates.

        Used by multiplexer.resync_from_source() to populate ARF
        without touching production vector databases.
        """
        return cls(
            enable_vector_handlers=False,
            enable_postgres_handler=False,
            skip_hash_updates=True,
            skip_cursor_updates=True,
        )

    @classmethod
    def replay_to_destination(cls, destination_id: UUID) -> "SyncExecutionConfig":
        """Replay from ARF to specific destination.

        Used by multiplexer.fork() to populate a shadow destination
        from ARF without re-fetching from source.
        """
        return cls(
            target_destinations=[destination_id],
            enable_raw_data_handler=False,
            skip_hash_comparison=True,
        )

