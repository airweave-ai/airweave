"""Sync multiplexing module - manages multiple destinations and replay operations.

This module provides:
- SyncMultiplexer: Manages destination slots for migrations and blue-green deployments
- ARFReplaySource: Pseudo-source that reads from ARF storage
- replay_to_destination: Replays entities to a specific destination

Typical migration workflow:
1. multiplexer.resync_from_source() - Ensure ARF is up-to-date
2. multiplexer.fork() - Create shadow destination, optionally replay from ARF
3. Validate shadow destination (search quality, etc.)
4. multiplexer.switch() - Promote shadow to active
5. (Optional) cleanup deprecated destinations
"""

from airweave.platform.sync.multiplex.multiplexer import SyncMultiplexer, get_multiplexer
from airweave.platform.sync.multiplex.replay import (
    ARFReplaySource,
    create_replay_orchestrator,
    replay_to_destination,
)

__all__ = [
    "SyncMultiplexer",
    "get_multiplexer",
    "ARFReplaySource",
    "replay_to_destination",
    "create_replay_orchestrator",
]
