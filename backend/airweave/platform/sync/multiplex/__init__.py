"""Sync multiplexing module - manages destination migrations and replay operations.

This module provides:
- ARFReplaySource: Pseudo-source that reads from ARF storage for replay operations

Typical replay workflow:
1. Ensure ARF is up-to-date (run normal sync first)
2. Create sync job for replay
3. Use SyncFactory.create_orchestrator(..., replay_target_destination_id=target_id)
4. Run orchestrator (handles replay via ARFReplaySource)
"""

from airweave.platform.sync.multiplex.replay import ARFReplaySource

__all__ = [
    "ARFReplaySource",
]
