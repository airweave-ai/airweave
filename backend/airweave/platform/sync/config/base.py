"""Sync configuration schemas with defaults.

All defaults are defined here in the schema - no external system owns defaults.
Uses Pydantic Settings for automatic env var loading.
"""

import warnings
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DestinationConfig(BaseModel):
    """Controls where entities are written."""

    skip_vespa: bool = Field(False, description="Skip writing to native Vespa")
    target_destinations: Optional[List[UUID]] = Field(
        None, description="If set, ONLY write to these destination UUIDs"
    )
    exclude_destinations: Optional[List[UUID]] = Field(
        None, description="Skip these destination UUIDs"
    )


class HandlerConfig(BaseModel):
    """Controls which handlers run during sync."""

    enable_vector_handlers: bool = Field(True, description="Enable VectorDBHandler")
    enable_raw_data_handler: bool = Field(True, description="Enable RawDataHandler (ARF)")
    enable_postgres_handler: bool = Field(True, description="Enable EntityPostgresHandler")


class CursorConfig(BaseModel):
    """Controls incremental sync cursor behavior."""

    skip_load: bool = Field(False, description="Don't load cursor (fetch all entities)")
    skip_updates: bool = Field(False, description="Don't persist cursor progress")


class BehaviorConfig(BaseModel):
    """Miscellaneous execution behavior flags."""

    skip_hash_comparison: bool = Field(False, description="Force INSERT for all entities")
    replay_from_arf: bool = Field(
        False, description="Replay from ARF storage instead of calling source"
    )
    skip_guardrails: bool = Field(False, description="Skip usage guardrails (entity count checks)")


class SyncConfig(BaseSettings):
    """Sync configuration with automatic env var loading.

    Env vars use double underscore as delimiter:
        SYNC_CONFIG__HANDLERS__ENABLE_VECTOR_HANDLERS=false
    """

    model_config = SettingsConfigDict(
        env_prefix="SYNC_CONFIG__",
        env_nested_delimiter="__",
        extra="ignore",
    )

    destinations: DestinationConfig = Field(default_factory=DestinationConfig)
    handlers: HandlerConfig = Field(default_factory=HandlerConfig)
    cursor: CursorConfig = Field(default_factory=CursorConfig)
    behavior: BehaviorConfig = Field(default_factory=BehaviorConfig)

    @model_validator(mode="after")
    def validate_config_logic(self):
        """Validate that config combinations make sense."""
        # Vespa must be enabled (sole vector database)
        if self.destinations.skip_vespa:
            raise ValueError(
                "Invalid config: skip_vespa is True. "
                "Vespa is the only vector database and must be enabled."
            )

        if self.destinations.target_destinations and self.destinations.exclude_destinations:
            overlap = set(self.destinations.target_destinations) & set(
                self.destinations.exclude_destinations
            )
            if overlap:
                raise ValueError(f"Destination conflict: {overlap} in both target and exclude")

        if self.destinations.target_destinations and self.handlers.enable_raw_data_handler:
            warnings.warn(
                "Writing to specific destinations with raw_data_handler enabled "
                "may duplicate ARF data.",
                stacklevel=2,
            )

        return self

    def merge_with(self, overrides: Optional[dict]) -> "SyncConfig":
        """Merge this config with overrides dict, returning new config.

        Args:
            overrides: Dict with partial config to merge. None values are ignored.

        Returns:
            New SyncConfig with overrides applied.
        """
        if not overrides:
            return self

        current = self.model_dump()
        _deep_merge(current, overrides)
        return SyncConfig(**current)

    # ========================================================================
    # PRESET FACTORIES
    # ========================================================================

    @classmethod
    def default(cls) -> "SyncConfig":
        """Normal sync to all destinations."""
        return cls()

    @classmethod
    def vespa_only(cls) -> "SyncConfig":
        """Write to Vespa only (default since Qdrant deprecation)."""
        return cls(destinations=DestinationConfig(skip_vespa=False))

    @classmethod
    def arf_capture_only(cls) -> "SyncConfig":
        """Capture to ARF without vector DBs or postgres."""
        return cls(
            handlers=HandlerConfig(
                enable_vector_handlers=False,
                enable_postgres_handler=False,
            ),
            cursor=CursorConfig(skip_load=True, skip_updates=True),
            behavior=BehaviorConfig(skip_hash_comparison=True),
        )

    @classmethod
    def replay_from_arf_to_vector_dbs(cls) -> "SyncConfig":
        """Replay from ARF to vector DBs only."""
        return cls(
            handlers=HandlerConfig(
                enable_vector_handlers=True,
                enable_raw_data_handler=False,
                enable_postgres_handler=False,
            ),
            cursor=CursorConfig(skip_load=True, skip_updates=True),
            behavior=BehaviorConfig(skip_hash_comparison=True, replay_from_arf=True),
        )


def _deep_merge(base: dict, overrides: dict) -> None:
    """Deep merge overrides into base dict, ignoring None values."""
    for key, value in overrides.items():
        if value is None:
            continue
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
