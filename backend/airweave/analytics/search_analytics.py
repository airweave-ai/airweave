"""Unified search analytics utilities for PostHog tracking."""

from typing import Any, Dict, List, Optional

from airweave.api.context import ApiContext


def build_search_properties(
    ctx: ApiContext,
    query: str,
    collection_slug: str,
    duration_ms: float,
    search_type: str = "regular",
    results: Optional[List[Dict]] = None,
    completion: Optional[str] = None,
    response_type: Optional[str] = None,
    status: str = "success",
    **additional_properties: Any,
) -> Dict[str, Any]:
    """Build unified search properties for PostHog tracking.

    Args:
        ctx: API context with analytics service
        query: Search query text
        collection_slug: Collection readable ID
        duration_ms: Search execution time
        search_type: "regular" or "streaming"
        results: Search results (optional)
        completion: AI-generated completion/answer (optional)
        response_type: Response type for legacy compatibility
        status: "success" or error status
        **additional_properties: Any additional properties to include

    Returns:
        Dict of properties ready for PostHog tracking
    """
    properties = {
        # Core search data
        "query_length": len(query),
        "collection_slug": collection_slug,
        "duration_ms": duration_ms,
        "search_type": search_type,
        "status": status,
        # Results data
        "results_count": len(results) if results else 0,
        # AI completion data
        "has_completion": completion is not None,
        "completion_length": len(completion) if completion else 0,
        # Context data (automatically included by ContextualAnalyticsService)
        "organization_name": ctx.organization.name,
        "auth_method": ctx.auth_method,
    }

    # Add response type for legacy compatibility
    if response_type:
        properties["response_type"] = response_type

    # Add any additional properties
    properties.update(additional_properties)

    return properties


def track_search_completion(
    ctx: ApiContext,
    query: str,
    collection_slug: str,
    duration_ms: float,
    results: List[Dict],
    search_type: str = "regular",
    completion: Optional[str] = None,
    response_type: Optional[str] = None,
    status: str = "success",
    **additional_properties: Any,
) -> None:
    """Track search completion with full analytics.

    Args:
        ctx: API context with analytics service
        query: Search query text
        collection_slug: Collection readable ID
        duration_ms: Search execution time
        results: Search results
        search_type: "regular" or "streaming"
        completion: AI-generated completion/answer (optional)
        response_type: Response type for legacy compatibility
        status: "success" or error status
        **additional_properties: Additional search properties
    """
    properties = build_search_properties(
        ctx=ctx,
        query=query,
        collection_slug=collection_slug,
        duration_ms=duration_ms,
        search_type=search_type,
        results=results,
        completion=completion,
        response_type=response_type,
        status=status,
        **additional_properties,
    )
    ctx.analytics.track_event("search_query", properties)
