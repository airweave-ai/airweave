"""Analytics module for PostHog integration."""

from .agentic_search_analytics import (
    build_agentic_search_properties,
    build_iteration_summaries,
    track_agentic_search_completion,
    track_agentic_search_error,
)
from .contextual_service import ContextualAnalyticsService, RequestHeaders
from .events.business_events import business_events
from .search_analytics import (
    build_search_properties,
    track_search_completion,
)
from .service import analytics

__all__ = [
    "analytics",
    "business_events",
    "ContextualAnalyticsService",
    "RequestHeaders",
    "build_agentic_search_properties",
    "build_iteration_summaries",
    "track_agentic_search_completion",
    "track_agentic_search_error",
    "build_search_properties",
    "track_search_completion",
]
