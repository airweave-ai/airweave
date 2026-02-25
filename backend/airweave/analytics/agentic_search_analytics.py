"""Agentic search analytics utilities for PostHog tracking.

Provides property builders and tracking functions for agentic search events,
following the same pattern as search_analytics.py for regular search.

Two events are tracked:
- agentic_search_query: Every completed agentic search (success)
- agentic_search_error: Unhandled failures during agentic search
"""

from typing import Any, Dict, List, Optional, Tuple

from airweave.analytics.service import analytics
from airweave.api.context import ApiContext


def build_agentic_search_properties(
    ctx: ApiContext,
    query: str,
    collection_slug: str,
    duration_ms: float,
    mode: str,
    total_iterations: int,
    had_consolidation: bool,
    exit_reason: str,
    results_count: int,
    answer_length: int,
    citations_count: int,
    timings: List[Tuple[str, int]],
    is_streaming: bool = False,
    has_user_filter: bool = False,
    user_filter_groups_count: int = 0,
    user_limit: Optional[int] = None,
    iteration_summaries: Optional[List[Dict[str, Any]]] = None,
    search_error_count: int = 0,
    total_prompt_tokens: Optional[int] = None,
    total_completion_tokens: Optional[int] = None,
    fallback_stats: Optional[Dict[str, Any]] = None,
    status: str = "success",
    **additional_properties: Any,
) -> Dict[str, Any]:
    """Build agentic search properties for PostHog tracking.

    Aggregates timing data, per-iteration summaries, token usage, fallback
    provider tracking, and context window utilization into a flat property
    dict suitable for
    PostHog dashboards.

    Args:
        ctx: API context with analytics service.
        query: The user's search query text.
        collection_slug: Collection readable ID.
        duration_ms: Total end-to-end execution time in milliseconds.
        mode: Search mode ("fast" or "thinking").
        total_iterations: Number of plan-search-evaluate iterations.
        had_consolidation: Whether a consolidation pass was triggered.
        exit_reason: Why the loop exited ("fast_mode", "answer_found", "consolidation").
        results_count: Number of results in the final response.
        answer_length: Character length of the composed answer.
        citations_count: Number of citations in the answer.
        timings: List of (label, ms) tuples from the agent's timing tracker.
        is_streaming: Whether this was a streaming request.
        has_user_filter: Whether the user supplied filter groups.
        user_filter_groups_count: Number of user-supplied filter groups.
        user_limit: User-requested result limit (None if not set).
        iteration_summaries: Per-iteration summary dicts (may include context_stats).
        search_error_count: Number of iterations with search errors.
        total_prompt_tokens: Cumulative LLM prompt tokens (None if unavailable).
        total_completion_tokens: Cumulative LLM completion tokens (None if unavailable).
        fallback_stats: Provider fallback tracking from FallbackChainLLM (None if single provider).
        status: "success" or error status.
        **additional_properties: Extra properties to include.

    Returns:
        Dict of properties ready for PostHog tracking.
    """
    properties: Dict[str, Any] = {
        # Core search data
        "query_length": len(query),
        "collection_slug": collection_slug,
        "duration_ms": duration_ms,
        "status": status,
        # Configuration
        "mode": mode,
        "is_streaming": is_streaming,
        "has_user_filter": has_user_filter,
        "user_filter_groups_count": user_filter_groups_count,
        "user_limit": user_limit,
        # Loop metrics
        "total_iterations": total_iterations,
        "had_consolidation": had_consolidation,
        "exit_reason": exit_reason,
        # Results & Answer
        "results_count": results_count,
        "answer_length": answer_length,
        "citations_count": citations_count,
        # Quality signals
        "had_search_errors": search_error_count > 0,
        "search_error_count": search_error_count,
        # Context
        "organization_name": ctx.organization.name,
        "auth_method": ctx.auth_method,
    }

    # Token usage (cumulative across all LLM calls: planner + evaluator + composer)
    if total_prompt_tokens is not None:
        properties["total_prompt_tokens"] = total_prompt_tokens
        properties["total_completion_tokens"] = total_completion_tokens or 0
        properties["total_tokens"] = total_prompt_tokens + (total_completion_tokens or 0)

    # LLM provider fallback tracking
    if fallback_stats is not None:
        properties["llm_primary_provider"] = fallback_stats.get("primary_provider")
        properties["llm_total_calls"] = fallback_stats.get("total_calls", 0)
        properties["llm_fallback_count"] = fallback_stats.get("fallback_count", 0)
        properties["llm_fallback_rate"] = fallback_stats.get("fallback_rate", 0.0)
        properties["llm_calls_per_provider"] = fallback_stats.get("calls_per_provider", {})
        properties["llm_had_fallback"] = fallback_stats.get("fallback_count", 0) > 0

    # Flatten and aggregate timing data
    _flatten_timings(properties, timings)

    # Add per-iteration summaries and derived metrics
    if iteration_summaries:
        properties["iterations"] = iteration_summaries
        strategies = [it.get("retrieval_strategy", "unknown") for it in iteration_summaries]
        properties["strategies_used"] = list(set(strategies))

        # Aggregate context window utilization metrics
        _aggregate_context_window_metrics(properties, iteration_summaries)

    properties.update(additional_properties)

    return properties


def _flatten_timings(properties: Dict[str, Any], timings: List[Tuple[str, int]]) -> None:
    """Aggregate and flatten timing data into PostHog properties.

    Produces both aggregated stage totals (for dashboards) and a full
    label-to-ms detail dict (for deep analysis).

    Args:
        properties: Properties dict to update in-place.
        timings: List of (label, ms) tuples from the agent.
    """
    total_planning_ms = 0
    total_embedding_ms = 0
    total_search_ms = 0
    total_evaluation_ms = 0
    composition_ms = 0
    build_metadata_ms = 0

    for label, ms in timings:
        if label == "build_collection_metadata":
            build_metadata_ms = ms
        elif label == "build_initial_state":
            pass  # Negligible, skip
        elif label.endswith("/plan"):
            total_planning_ms += ms
        elif label.endswith("/embed"):
            total_embedding_ms += ms
        elif label.endswith(("/compile", "/execute", "/search_error")):
            total_search_ms += ms
        elif label.endswith("/evaluate"):
            total_evaluation_ms += ms
        elif label == "compose":
            composition_ms = ms

    properties["build_metadata_ms"] = build_metadata_ms
    properties["total_planning_ms"] = total_planning_ms
    properties["total_embedding_ms"] = total_embedding_ms
    properties["total_search_ms"] = total_search_ms
    properties["total_evaluation_ms"] = total_evaluation_ms
    properties["composition_ms"] = composition_ms

    # Full detail for deep analysis
    properties["timings_detail"] = dict(timings)


def _aggregate_context_window_metrics(
    properties: Dict[str, Any],
    iteration_summaries: List[Dict[str, Any]],
) -> None:
    """Compute aggregate context window utilization metrics.

    Extracts per-iteration context stats (planner history fit, evaluator
    results/history fit) and produces top-level aggregates for dashboards.

    Args:
        properties: Properties dict to update in-place.
        iteration_summaries: Per-iteration summaries (may contain context stats).
    """
    evaluator_results_coverages: List[float] = []
    context_truncated_count = 0

    for it in iteration_summaries:
        # Check evaluator results coverage
        results_shown = it.get("evaluator_results_shown")
        results_total = it.get("evaluator_results_total")
        if results_shown is not None and results_total is not None and results_total > 0:
            coverage = results_shown / results_total
            evaluator_results_coverages.append(coverage)
            if results_shown < results_total:
                context_truncated_count += 1

        # Check planner history truncation
        planner_shown = it.get("planner_history_shown")
        planner_total = it.get("planner_history_total")
        if (
            planner_shown is not None
            and planner_total is not None
            and planner_total > 0
            and planner_shown < planner_total
        ):
            context_truncated_count += 1

    if evaluator_results_coverages:
        properties["min_evaluator_results_pct"] = round(min(evaluator_results_coverages) * 100, 1)
        properties["avg_evaluator_results_pct"] = round(
            sum(evaluator_results_coverages) / len(evaluator_results_coverages) * 100, 1
        )

    properties["context_truncated_count"] = context_truncated_count


def build_iteration_summaries(
    history: Any,
    current_iteration: Any,
    current_iteration_number: int,
    is_fast_mode: bool,
    context_stats: Optional[List[Dict[str, int]]] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """Build per-iteration summary dicts from agentic search state.

    Extracts compact metadata from each completed iteration in history
    and from the final (current) iteration. Merges context window stats
    (planner/evaluator visibility) when provided.

    Args:
        history: AgenticSearchHistory or None.
        current_iteration: AgenticSearchCurrentIteration (the last iteration).
        current_iteration_number: The iteration number of the current iteration.
        is_fast_mode: Whether the search ran in fast mode.
        context_stats: Per-iteration context window stats collected during the
            agent loop. Each dict may contain: planner_history_shown/total,
            evaluator_results_shown/total, evaluator_history_shown/total.

    Returns:
        Tuple of (iteration_summaries, search_error_count).
    """
    summaries: List[Dict[str, Any]] = []
    search_error_count = 0

    # Add completed iterations from history
    if history is not None:
        for iter_num in sorted(history.iterations.keys()):
            iteration = history.iterations[iter_num]
            summary: Dict[str, Any] = {
                "iteration_number": iter_num,
                "retrieval_strategy": (
                    iteration.plan.retrieval_strategy.value if iteration.plan else None
                ),
                "query_variations_count": (
                    len(iteration.plan.query.variations) if iteration.plan else 0
                ),
                "filter_groups_count": (len(iteration.plan.filter_groups) if iteration.plan else 0),
                "results_count": (
                    iteration.result_brief.total_count if iteration.result_brief else 0
                ),
                "had_search_error": iteration.search_error is not None,
            }

            if iteration.search_error is not None:
                search_error_count += 1

            if iteration.evaluation:
                summary["should_continue"] = iteration.evaluation.should_continue
                summary["answer_found"] = iteration.evaluation.answer_found

            summaries.append(summary)

    # Add current (final) iteration which is not yet in history
    current_plan = current_iteration.plan
    current_results = current_iteration.search_results
    current_summary: Dict[str, Any] = {
        "iteration_number": current_iteration_number,
        "retrieval_strategy": (current_plan.retrieval_strategy.value if current_plan else None),
        "query_variations_count": (len(current_plan.query.variations) if current_plan else 0),
        "filter_groups_count": (len(current_plan.filter_groups) if current_plan else 0),
        "results_count": len(current_results) if current_results else 0,
        "had_search_error": current_iteration.search_error is not None,
    }

    if current_iteration.search_error is not None:
        search_error_count += 1

    # Current iteration may have an evaluation (THINKING mode, non-consolidation)
    if current_iteration.evaluation and not is_fast_mode:
        current_summary["should_continue"] = current_iteration.evaluation.should_continue
        current_summary["answer_found"] = current_iteration.evaluation.answer_found

    summaries.append(current_summary)

    # Merge context window stats into summaries (matched by index)
    if context_stats:
        for i, stats in enumerate(context_stats):
            if i < len(summaries):
                summaries[i].update(stats)

    return summaries, search_error_count


def track_agentic_search_completion(
    ctx: ApiContext,
    query: str,
    collection_slug: str,
    duration_ms: float,
    mode: str,
    total_iterations: int,
    had_consolidation: bool,
    exit_reason: str,
    results_count: int,
    answer_length: int,
    citations_count: int,
    timings: List[Tuple[str, int]],
    is_streaming: bool = False,
    has_user_filter: bool = False,
    user_filter_groups_count: int = 0,
    user_limit: Optional[int] = None,
    iteration_summaries: Optional[List[Dict[str, Any]]] = None,
    search_error_count: int = 0,
    total_prompt_tokens: Optional[int] = None,
    total_completion_tokens: Optional[int] = None,
    fallback_stats: Optional[Dict[str, Any]] = None,
    **additional_properties: Any,
) -> None:
    """Track a completed agentic search with full analytics.

    Args:
        ctx: API context with analytics service.
        query: The user's search query text.
        collection_slug: Collection readable ID.
        duration_ms: Total end-to-end execution time in milliseconds.
        mode: Search mode ("fast" or "thinking").
        total_iterations: Number of plan-search-evaluate iterations.
        had_consolidation: Whether a consolidation pass was triggered.
        exit_reason: Why the loop exited.
        results_count: Number of results in the final response.
        answer_length: Character length of the composed answer.
        citations_count: Number of citations in the answer.
        timings: List of (label, ms) tuples from the agent.
        is_streaming: Whether this was a streaming request.
        has_user_filter: Whether the user supplied filter groups.
        user_filter_groups_count: Number of user-supplied filter groups.
        user_limit: User-requested result limit.
        iteration_summaries: Per-iteration summary dicts.
        search_error_count: Number of iterations with search errors.
        total_prompt_tokens: Cumulative LLM prompt tokens.
        total_completion_tokens: Cumulative LLM completion tokens.
        fallback_stats: Provider fallback tracking from FallbackChainLLM.
        **additional_properties: Extra properties to include.
    """
    properties = build_agentic_search_properties(
        ctx=ctx,
        query=query,
        collection_slug=collection_slug,
        duration_ms=duration_ms,
        mode=mode,
        total_iterations=total_iterations,
        had_consolidation=had_consolidation,
        exit_reason=exit_reason,
        results_count=results_count,
        answer_length=answer_length,
        citations_count=citations_count,
        timings=timings,
        is_streaming=is_streaming,
        has_user_filter=has_user_filter,
        user_filter_groups_count=user_filter_groups_count,
        user_limit=user_limit,
        iteration_summaries=iteration_summaries,
        search_error_count=search_error_count,
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        fallback_stats=fallback_stats,
        **additional_properties,
    )
    analytics.track_event("agentic_search_query", properties, ctx=ctx)


def track_agentic_search_error(
    ctx: ApiContext,
    query: str,
    collection_slug: str,
    duration_ms: float,
    mode: str,
    error_message: str,
    error_type: str,
    is_streaming: bool = False,
) -> None:
    """Track an agentic search that failed with an unhandled exception.

    Args:
        ctx: API context with analytics service.
        query: The user's search query text.
        collection_slug: Collection readable ID.
        duration_ms: Time elapsed before the error occurred.
        mode: Search mode ("fast" or "thinking").
        error_message: The exception message.
        error_type: The exception class name.
        is_streaming: Whether this was a streaming request.
    """
    properties: Dict[str, Any] = {
        "query_length": len(query),
        "collection_slug": collection_slug,
        "duration_ms": duration_ms,
        "mode": mode,
        "is_streaming": is_streaming,
        "error_message": error_message,
        "error_type": error_type,
        "status": "error",
        "organization_name": ctx.organization.name,
        "auth_method": ctx.auth_method,
    }
    analytics.track_event("agentic_search_error", properties, ctx=ctx)
