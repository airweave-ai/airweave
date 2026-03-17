"""Sync runtime — per-sync mutable state.

Separated from SyncContext (frozen data) so that context is pure data
and runtime holds only per-sync mutable state.

Stateless app-scoped services (event_bus, usage_checker, embedders)
are injected directly into their consumers via constructor DI.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.cursor import SyncCursor
    from airweave.domains.sync_pipeline.pipeline.entity_tracker import EntityTracker
    from airweave.platform.destinations._base import BaseDestination
    from airweave.platform.sources._base import BaseSource


@dataclass
class SyncRuntime:
    """Per-sync mutable state.

    Built by SyncFactory alongside SyncContext.
    Contains only per-sync stateful objects — stateless singletons
    (event_bus, usage_checker, embedders) are DI'd directly into consumers.
    """

    source: "BaseSource"
    cursor: "SyncCursor"
    entity_tracker: "EntityTracker"
    destinations: List["BaseDestination"] = field(default_factory=list)
