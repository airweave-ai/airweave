"""Sync execution configuration for controlling sync behavior."""

import warnings
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class SyncExecutionConfig(BaseModel):
    """Declarative sync execution configuration.

    Each component reads only the flags it needs - highly modular.
    Config is persisted in sync_job.execution_config_json to avoid Temporal bloat.
    """

    # Destination selection
    target_destinations: Optional[List[UUID]] = Field(
        None, description="If set, ONLY write to these destinations"
    )
    exclude_destinations: Optional[List[UUID]] = Field(None, description="Skip these destinations")
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
    skip_hash_updates: bool = Field(False, description="Don't update content_hash column")
    skip_cursor_load: bool = Field(False, description="Don't load cursor (fetch all entities)")
    skip_cursor_updates: bool = Field(
        False, description="Don't save cursor progress (for ARF-only syncs)"
    )

    # Performance
    max_workers: int = Field(20, description="Max concurrent workers")
    batch_size: int = Field(100, description="Entity batch size")

    @model_validator(mode="after")
    def validate_config_logic(self):
        """Validate that config combinations make sense."""

        # 1. Validate destination_strategy is a known value
        valid_strategies = {"active_only", "shadow_only", "all", "active_and_shadow"}
        if self.destination_strategy not in valid_strategies:
            raise ValueError(
                f"destination_strategy must be one of {valid_strategies}, "
                f"got '{self.destination_strategy}'"
            )

        # 2. Warn if target_destinations overrides destination_strategy
        if self.target_destinations and self.destination_strategy != "active_and_shadow":
            warnings.warn(
                f"destination_strategy='{self.destination_strategy}' is ignored when "
                f"target_destinations is set. Explicitly listing destinations takes precedence.",
                stacklevel=2,
            )

        # 3. Detect conflicts between target and exclude destinations
        if self.target_destinations and self.exclude_destinations:
            overlap = set(self.target_destinations) & set(self.exclude_destinations)
            if overlap:
                raise ValueError(
                    f"Cannot have same destination in both target_destinations and "
                    f"exclude_destinations: {overlap}"
                )

        # 4. Warn about replay configs that re-write to ARF
        if self.target_destinations and self.enable_raw_data_handler:
            warnings.warn(
                "Replay to specific destination typically disables raw_data_handler. "
                "You're writing the same data to ARF again. Is this intended?",
                stacklevel=2,
            )

        # 5. Warn about unusual cursor skip combination
        if self.skip_cursor_updates and not self.skip_hash_updates:
            warnings.warn(
                "skip_cursor_updates=True but skip_hash_updates=False. "
                "This means next sync will use old cursor but compare new hashes. "
                "Typically both are skipped together (e.g., arf_capture_only).",
                stacklevel=2,
            )

        return self

    @classmethod
    def default(cls) -> "SyncExecutionConfig":
        """Normal sync to active+shadow destinations."""
        return cls()

    @classmethod
    def arf_capture_only(cls) -> "SyncExecutionConfig":
        """Capture to ARF without vector DBs or hash updates.

        Used by multiplexer.resync_from_source() to populate ARF
        without touching production vector databases. Fetches all entities
        (skips cursor) to ensure complete ARF backfill.
        """
        return cls(
            enable_vector_handlers=False,
            enable_postgres_handler=False,
            skip_hash_updates=True,
            skip_cursor_load=True,
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

    @classmethod
    def dry_run(cls) -> "SyncExecutionConfig":
        """Validate source without writing anywhere.

        Use cases:
        - Test source credentials
        - Validate entity schemas
        - Count entities before full sync
        - Performance testing

        Note: All handlers disabled, but sync will still execute
        entity fetching and transformation logic.
        """
        return cls(
            enable_vector_handlers=False,
            enable_raw_data_handler=False,
            enable_postgres_handler=False,
            skip_hash_updates=True,
            skip_cursor_load=True,
            skip_cursor_updates=True,
        )
