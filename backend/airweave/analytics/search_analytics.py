"""Shared analytics utilities for search operations."""

from typing import Any, Dict, Optional

from airweave.analytics.service import analytics
from airweave.api.context import ApiContext


def build_search_properties(
    ctx: ApiContext,
    query: str,
    collection_slug: str,
    duration_ms: float,
    search_type: str = "regular",
    results: Optional[list] = None,
    response_type: Optional[str] = None,
    status: str = "success",
) -> Dict[str, Any]:
    """Build unified analytics properties for search operations.

    Args:
        ctx: API context with user and organization info
        query: Search query text
        collection_slug: Collection identifier
        duration_ms: Search duration in milliseconds
        search_type: Type of search ("regular" or "streaming")
        results: Search results list (optional)
        response_type: Response type (optional)
        status: Search status (default: "success")

    Returns:
        Dictionary of analytics properties
    """
    properties = {
        "query": query,  # Full query text for PostHog history
        "query_length": len(query),
        "collection_slug": collection_slug,
        "duration_ms": duration_ms,
        "search_type": search_type,
        "organization_name": getattr(ctx.organization, "name", "unknown"),
        "status": status,
    }

    # Add response type if provided
    if response_type:
        properties["response_type"] = response_type

    # Add results count if results are provided
    if results:
        properties["results_count"] = len(results)

    return properties


def build_search_error_properties(
    query: str,
    collection_slug: str,
    duration_ms: float,
    error: Exception,
    search_type: str = "regular",
) -> Dict[str, Any]:
    """Build analytics properties for search errors.

    Args:
        query: Search query text
        collection_slug: Collection identifier
        duration_ms: Search duration in milliseconds
        error: The exception that occurred
        search_type: Type of search ("regular" or "streaming")

    Returns:
        Dictionary of analytics properties
    """
    return {
        "query": query,  # Full query text for PostHog history
        "query_length": len(query) if query else 0,
        "collection_slug": collection_slug,
        "duration_ms": duration_ms,
        "search_type": search_type,
        "error": type(error).__name__,
    }


def track_search_event(
    ctx: ApiContext,
    properties: Dict[str, Any],
    event_name: str,
) -> None:
    """Track a search analytics event.

    Args:
        ctx: API context with user and organization info
        properties: Analytics properties dictionary
        event_name: Name of the event to track
    """
    analytics.track_event(
        event_name=event_name,
        distinct_id=str(ctx.user.id) if ctx.user else f"api_key_{ctx.organization.id}",
        properties=properties,
        groups={"organization": str(ctx.organization.id)},
    )
