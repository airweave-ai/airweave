"""Context and dispatcher builders for platform operations.

Builders are factory classes that construct context objects and dispatchers.

Context Builders:
- ScopeContextBuilder: Creates ScopeContext
- InfraContextBuilder: Creates InfraContext
- SourceContextBuilder: Creates SourceContext
- DestinationsContextBuilder: Creates DestinationsContext
- TrackingContextBuilder: Creates TrackingContext
- SyncContextBuilder: Orchestrates all builders to create SyncContext
- CleanupContextBuilder: Creates CleanupContext for deletion operations

Dispatcher Builders:
- DispatcherBuilder: Creates ActionDispatcher with handlers
"""

from airweave.platform.builders.cleanup import CleanupContextBuilder
from airweave.platform.builders.destinations import DestinationsContextBuilder
from airweave.platform.builders.dispatcher import DispatcherBuilder
from airweave.platform.builders.infra import InfraContextBuilder
from airweave.platform.builders.scope import ScopeContextBuilder
from airweave.platform.builders.source import SourceContextBuilder
from airweave.platform.builders.sync import SyncContextBuilder
from airweave.platform.builders.tracking import TrackingContextBuilder

__all__ = [
    "CleanupContextBuilder",
    "DestinationsContextBuilder",
    "DispatcherBuilder",
    "InfraContextBuilder",
    "ScopeContextBuilder",
    "SourceContextBuilder",
    "SyncContextBuilder",
    "TrackingContextBuilder",
]
