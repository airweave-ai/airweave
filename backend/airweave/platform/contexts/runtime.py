"""Sync runtime - live services for a sync run.

Separated from SyncContext (frozen data) so that context is pure data
and runtime holds mutable state and service references.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from airweave.core.guard_rail_service import GuardRailService
    from airweave.platform.destinations._base import BaseDestination
    from airweave.platform.sources._base import BaseSource
    from airweave.platform.sync.cursor import SyncCursor
    from airweave.platform.sync.pipeline.entity_tracker import EntityTracker
    from airweave.platform.sync.state_publisher import SyncStatePublisher


@dataclass
class SyncRuntime:
    """Live services and mutable state for a sync run.

    Built by SyncContextBuilder alongside SyncContext.
    Held by SyncOrchestrator and injected into pipeline/handler constructors.
    """

    source: "BaseSource"
    cursor: "SyncCursor"
    destinations: List["BaseDestination"] = field(default_factory=list)
    entity_tracker: "EntityTracker" = None
    state_publisher: "SyncStatePublisher" = None
    guard_rail: "GuardRailService" = None
