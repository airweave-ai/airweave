"""Sync module for Airweave.

Provides:
- SyncFactory: Creates orchestrators (from sync.factory import SyncFactory)
- SyncOrchestrator: Coordinates the entire sync workflow
- EntityPipeline: Processes entities through transformation stages
- SyncContext: Immutable container for sync resources
- RawDataService: Stores raw entities with entity-level granularity

Multiplexing (import from sync.multiplex directly):
- SyncMultiplexer: Manages multiple destinations per sync (migrations)
- ARFReplaySource: Pseudo-source for replaying from ARF
- replay_to_destination: Replays entities from ARF to destinations
"""

from airweave.platform.sync.raw_data import (
    RawDataService,
    SyncManifest,
    raw_data_service,
)

__all__ = [
    "RawDataService",
    "raw_data_service",
    "SyncManifest",
]
