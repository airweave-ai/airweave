"""Sync runtime - live services for a sync run.

Separated from SyncContext (frozen data) so that context is pure data
and runtime holds mutable state and service references.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

from airweave.domains.usage.protocols import UsageLimitCheckerProtocol

if TYPE_CHECKING:
    from airweave.core.protocols.event_bus import EventBus
    from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
    from airweave.platform.destinations._base import BaseDestination
    from airweave.platform.sources._base import BaseSource
    from airweave.platform.sync.cursor import SyncCursor
    from airweave.platform.sync.pipeline.entity_tracker import EntityTracker


@dataclass
class SyncRuntime:
    """Live services and mutable state for a sync run.

    Built by SyncFactory alongside SyncContext.
    Held by SyncOrchestrator and injected into pipeline/handler constructors.
    """

    # Required — always set by factory
    source: "BaseSource"
    cursor: "SyncCursor"
    entity_tracker: "EntityTracker"
    event_bus: "EventBus"
    usage_checker: "UsageLimitCheckerProtocol"

    # Optional / defaulted
    dense_embedder: Optional["DenseEmbedderProtocol"] = None
    sparse_embedder: Optional["SparseEmbedderProtocol"] = None
    destinations: List["BaseDestination"] = field(default_factory=list)
