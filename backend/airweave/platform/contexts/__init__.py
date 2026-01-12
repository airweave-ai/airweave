"""Composable contexts for platform operations.

Contexts are dataclass containers that group related dependencies.
They are composable - one context may contain multiple sub-contexts.

Context Types:
- ScopeContext: Scopes operations (sync_id, collection_id, organization_id)
- InfraContext: Core infrastructure (ctx, logger)
- SourceContext: Source pipeline (source instance, cursor)
- DestinationsContext: Destination pipeline (destinations, entity_map)
- TrackingContext: Progress tracking (entity_tracker, state_publisher, guard_rail)
- BatchContext: Batch processing settings
- SyncContext: Full sync context (composes all above)
- CleanupContext: Minimal context for deletion operations

For execution behavior (handlers, destinations, cursor), see SyncConfig.
"""

from airweave.platform.contexts.batch import BatchContext
from airweave.platform.contexts.cleanup import CleanupContext
from airweave.platform.contexts.destinations import DestinationsContext
from airweave.platform.contexts.infra import InfraContext
from airweave.platform.contexts.scope import ScopeContext
from airweave.platform.contexts.source import SourceContext
from airweave.platform.contexts.sync import SyncContext
from airweave.platform.contexts.tracking import TrackingContext

__all__ = [
    "BatchContext",
    "CleanupContext",
    "DestinationsContext",
    "HandlerContext",
    "InfraContext",
    "ScopeContext",
    "SourceContext",
    "SyncContext",
    "TrackingContext",
]
