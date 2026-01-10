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

    # Destination selection (by UUID - advanced)
    target_destinations: Optional[List[UUID]] = Field(
        None, description="If set, ONLY write to these destinations"
    )
    exclude_destinations: Optional[List[UUID]] = Field(None, description="Skip these destinations")

    # Native vector DB toggles (simple boolean flags)
    skip_qdrant: bool = Field(False, description="Skip writing to native Qdrant destination")
    skip_vespa: bool = Field(False, description="Skip writing to native Vespa destination")

    # Handler toggles
    enable_vector_handlers: bool = Field(True, description="Enable VectorDBHandler")
    enable_raw_data_handler: bool = Field(True, description="Enable RawDataHandler (ARF)")
    enable_postgres_handler: bool = Field(True, description="Enable EntityPostgresHandler")

    # Behavior flags
    skip_hash_comparison: bool = Field(False, description="Force INSERT for all entities")
    skip_cursor_load: bool = Field(False, description="Don't load cursor (fetch all entities)")
    skip_cursor_updates: bool = Field(
        False, description="Don't save cursor progress (for ARF-only syncs)"
    )

    # ARF replay mode
    replay_from_arf: bool = Field(
        False,
        description="Replay entities from ARF storage instead of calling the source. "
        "Uses the sync's existing ARF data.",
    )

    # Guardrail bypass (admin-only)
    skip_guardrails: bool = Field(
        False,
        description="Skip guardrail checks (entity limits, payment status). Admin-only for backfills.",
    )

    @model_validator(mode="after")
    def validate_config_logic(self):
        """Validate that config combinations make sense."""
        # 1. Detect conflicts between target and exclude destinations
        if self.target_destinations and self.exclude_destinations:
            overlap = set(self.target_destinations) & set(self.exclude_destinations)
            if overlap:
                raise ValueError(
                    f"Cannot have same destination in both target_destinations and "
                    f"exclude_destinations: {overlap}"
                )

        # 2. Warn about replay configs that re-write to ARF
        if self.target_destinations and self.enable_raw_data_handler:
            warnings.warn(
                "Writing to specific destinations with raw_data_handler enabled "
                "may duplicate ARF data. Consider disable_raw_data_handler if "
                "replaying from ARF.",
                stacklevel=2,
            )

        return self

    @classmethod
    def default(cls) -> "SyncExecutionConfig":
        """Normal sync to all destinations (Qdrant + Vespa)."""
        return cls()

    @classmethod
    def qdrant_only(cls) -> "SyncExecutionConfig":
        """Write to Qdrant only, skip Vespa."""
        return cls(skip_vespa=True)

    @classmethod
    def vespa_only(cls) -> "SyncExecutionConfig":
        """Write to Vespa only, skip Qdrant."""
        return cls(skip_qdrant=True)

    @classmethod
    def arf_capture_only(cls) -> "SyncExecutionConfig":
        """Capture to ARF without vector DBs or postgres metadata.

        Fetches all entities (skips cursor) to ensure complete ARF backfill.
        Skips hash comparison to force all entities to be captured, not just changed ones.
        Disables postgres handler so no metadata/hashes are written to database.
        Useful for backfilling ARF storage without impacting production databases.
        """
        return cls(
            enable_vector_handlers=False,
            enable_postgres_handler=False,
            skip_hash_comparison=True,
            skip_cursor_load=True,
            skip_cursor_updates=True,
        )

    @classmethod
    def replay_from_arf_to_vector_dbs(cls) -> "SyncExecutionConfig":
        """Replay entities from ARF to all vector DBs only.

        Reads entities from ARF storage instead of calling the source.
        Disables ARF handler to avoid re-capturing data we're reading from.
        Disables postgres handler - only writes to vector DBs, no metadata changes.
        Skips hash comparison since we're bypassing postgres entirely.
        Skips cursor since we're replaying all entities.
        """
        return cls(
            replay_from_arf=True,
            enable_vector_handlers=True,
            enable_raw_data_handler=False,
            enable_postgres_handler=False,
            skip_hash_comparison=True,
            skip_cursor_load=True,
            skip_cursor_updates=True,
        )
