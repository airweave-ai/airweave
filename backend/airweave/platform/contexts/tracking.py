"""Tracking context for sync operations."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from airweave.domains.usage.protocols import UsageEnforcementProtocol
    from airweave.platform.sync.pipeline.entity_tracker import EntityTracker
    from airweave.platform.sync.state_publisher import SyncStatePublisher


@dataclass
class TrackingContext:
    """Progress tracking - only needed during active sync.

    Attributes:
        entity_tracker: Centralized entity state tracker
        state_publisher: Publishes progress to Redis pubsub
        usage_service: Usage enforcement service (optional)
    """

    entity_tracker: "EntityTracker"
    state_publisher: "SyncStatePublisher"
    usage_service: Optional["UsageEnforcementProtocol"] = None
