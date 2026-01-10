"""Sync configuration module with layered overrides.

Resolution order (lowest → highest priority):
1. Schema defaults (SyncConfig field defaults)
2. Environment (SYNC_CONFIG__* env vars)
3. Collection (collection.sync_config)
4. Sync (sync.sync_config)
5. SyncJob (sync_job.sync_config)

Env vars use double underscore delimiter:
    SYNC_CONFIG__DESTINATIONS__SKIP_QDRANT=true
    SYNC_CONFIG__HANDLERS__ENABLE_VECTOR_HANDLERS=false
    SYNC_CONFIG__CURSOR__SKIP_LOAD=true
    SYNC_CONFIG__BEHAVIOR__REPLAY_FROM_ARF=true

Usage:
    from airweave.platform.sync.config import SyncConfig, SyncConfigBuilder

    # Build config with all layers (sync_config is already typed as SyncConfig)
    config = SyncConfigBuilder.build(
        collection_overrides=collection.sync_config,
        sync_overrides=sync.sync_config,
        job_overrides=sync_job.sync_config,
    )

    # Use preset
    config = SyncConfig.arf_capture_only()

    # Direct config with env var loading
    config = SyncConfig()  # Reads SYNC_CONFIG__* env vars automatically
"""

from airweave.platform.sync.config.base import (
    BehaviorConfig,
    CursorConfig,
    DestinationConfig,
    HandlerConfig,
    SyncConfig,
)
from airweave.platform.sync.config.builder import SyncConfigBuilder

# Backwards compatibility alias - TODO: remove after migration
SyncExecutionConfig = SyncConfig

__all__ = [
    # Main config
    "SyncConfig",
    # Sub-configs
    "DestinationConfig",
    "HandlerConfig",
    "CursorConfig",
    "BehaviorConfig",
    # Builder
    "SyncConfigBuilder",
    # Backwards compatibility
    "SyncExecutionConfig",
]
