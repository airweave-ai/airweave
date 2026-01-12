"""Tracking context for sync operations."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from airweave.core.guard_rail_service import GuardRailService
    from airweave.platform.sync.pipeline.entity_tracker import EntityTracker
    from airweave.platform.sync.state_publisher import SyncStatePublisher


@dataclass
class TrackingContext:
    """Progress tracking - only needed during active sync.

    Attributes:
        entity_tracker: Centralized entity state tracker
        state_publisher: Publishes progress to Redis pubsub
        guard_rail: Rate limiting service (optional)
    """

    entity_tracker: "EntityTracker"
    state_publisher: "SyncStatePublisher"
    guard_rail: Optional["GuardRailService"] = None
