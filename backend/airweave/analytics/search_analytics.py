"""Unified search analytics utilities for PostHog tracking."""

import re
from typing import Any, Dict, List, Optional

from airweave.analytics.service import analytics
from airweave.api.context import ApiContext


def _to_snake_case(name: str) -> str:
    """Convert CamelCase operation name to snake_case.

    Examples:
        QueryExpansion -> query_expansion
        EmbedQuery -> embed_query
        FederatedSearch -> federated_search
    """
    # Insert underscores before capital letters (except first)
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    # Insert underscores before capital letters that follow lowercase
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


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
    state: Optional[Dict[str, Any]] = None,
    **additional_properties: Any,
) -> Dict[str, Any]:
    """Build unified search properties for PostHog tracking.

    Automatically extracts and flattens operation metrics from the state dict,
    providing comprehensive analytics data with zero maintenance overhead.

    Args:
        ctx: API context with analytics service
        query: Search query text
        collection_slug: Collection readable ID
        duration_ms: Search execution time
        search_type: "regular" or "streaming"
        results: Search results (optional)
        completion: AI-generated completion/answer (optional, full text tracked)
        response_type: Response type for legacy compatibility
        status: "success" or error status
        state: State dict containing operation metrics (optional)
        **additional_properties: Any additional properties to include

    Returns:
        Dict of properties ready for PostHog tracking with:
        - Top-level aggregates (easy filtering)
        - Operation timing breakdown
        - Operation-specific metrics
        - Provider usage tracking
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
        "completion_text": completion if completion else None,
        # Context data (automatically included by ContextualAnalyticsService)
        "organization_name": ctx.organization.name,
        "auth_method": ctx.auth_method,
    }

    # Add response type for legacy compatibility
    if response_type:
        properties["response_type"] = response_type

    # Automatically extract and flatten operation metrics from state
    if state:
        _flatten_operation_metrics(properties, state)

    # Add any additional properties (search config from service)
    properties.update(additional_properties)

    return properties


def _flatten_operation_metrics(properties: Dict[str, Any], state: Dict[str, Any]) -> None:
    """Automatically flatten operation metrics into PostHog properties.

    Extracts metrics from state and flattens them into a structure that's:
    - Easy to query in PostHog
    - Automatic (no manual updates needed)
    - Comprehensive (captures all operation data)

    Args:
        properties: Properties dict to update
        state: State dict containing operation metrics
    """
    # Extract operation metrics
    operation_metrics = state.get("operation_metrics", {})
    if not operation_metrics:
        return

    # Initialize timing dict
    properties["operation_timings"] = {}

    # Derive top-level aggregates for easy filtering
    retrieval_metrics = operation_metrics.get("Retrieval", {})
    reranking_metrics = operation_metrics.get("Reranking", {})
    federated_metrics = operation_metrics.get("FederatedSearch", {})

    # Key metrics for CTO dashboard
    properties["retrieval_count"] = retrieval_metrics.get("output_count", 0)
    properties["rerank_input_count"] = reranking_metrics.get("input_count", 0)
    properties["rerank_output_count"] = reranking_metrics.get("output_count", 0)
    properties["federated_count"] = federated_metrics.get("federated_count", 0)

    # Flatten each operation's metrics
    for op_name, metrics in operation_metrics.items():
        op_snake = _to_snake_case(op_name)

        # Extract and store timing (captured by orchestrator)
        duration = metrics.get("duration_ms")
        if duration is not None:
            rounded_duration = round(duration, 2)
            # Store in nested dict for context
            properties["operation_timings"][f"{op_snake}_ms"] = rounded_duration
            # ALSO store at top level for PostHog graphs/series
            properties[f"{op_snake}_ms"] = rounded_duration

        # Flatten operation-specific metrics
        for key, value in metrics.items():
            if key == "duration_ms":
                continue  # Already handled above

            # Create flattened property name
            prop_name = f"{op_snake}_{key}"
            properties[prop_name] = value

    # Extract provider usage (captured by fallback method)
    provider_usage = state.get("provider_usage", {})
    if provider_usage:
        # Keep nested structure for full context
        properties["providers_used"] = provider_usage

        # Add flat properties for easy PostHog filtering/grouping
        # This makes it easy to filter by specific provider or build dashboards
        for op_name, provider_name in provider_usage.items():
            op_snake = _to_snake_case(op_name)
            properties[f"provider_{op_snake}"] = provider_name

        # Track if any fallback occurred
        properties["had_provider_fallback"] = len(set(provider_usage.values())) > 1
        properties["fallback_operations"] = (
            [
                op
                for op, provider in provider_usage.items()
                if provider != list(provider_usage.values())[0]
            ]
            if len(set(provider_usage.values())) > 1
            else []
        )


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
    state: Optional[Dict[str, Any]] = None,
    **additional_properties: Any,
) -> None:
    """Track search completion with full analytics.

    Automatically extracts operation metrics from state for comprehensive tracking.

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
        state: State dict containing operation metrics (optional)
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
        state=state,  # Pass state for automatic metrics extraction
        **additional_properties,
    )
    analytics.track_event("search_query", properties, ctx=ctx)
