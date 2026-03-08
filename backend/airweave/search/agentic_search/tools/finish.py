"""Review and return tools for the agentic search agent.

Two separate tools:
- review_marked_results: Shows what's currently marked. Optional, non-terminal.
- return_results_to_user: Ends the loop immediately. Final.
"""

from typing import Any

from airweave.search.agentic_search.schemas.search_result import AgenticSearchResult
from airweave.search.agentic_search.schemas.state import AgenticSearchState
from airweave.search.agentic_search.tools.search import (
    _estimate_available_tokens,
    format_results_for_context,
)

# ── Tool definitions (sent to the LLM) ───────────────────────────────

REVIEW_MARKED_RESULTS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "review_marked_results",
        "description": (
            "Review what you have marked so far. Shows all marked results with "
            "their full content so you can verify correctness before returning. "
            "Does not end the search — you can continue searching, marking, or "
            "unmarking after reviewing."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}

RETURN_RESULTS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "return_results_to_user",
        "description": (
            "Return the marked results to the user and end the search. "
            "This is final — the search loop ends immediately. "
            "You can call mark_as_relevant and return_results_to_user "
            "in the same response."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}


# ── Handlers ─────────────────────────────────────────────────────────


def handle_review_marked_results(
    state: AgenticSearchState,
    messages: list[dict],
    context_window_tokens: int,
) -> str:
    """Handle a review_marked_results tool call. Returns review text."""
    return _build_review(state, messages, context_window_tokens)


def handle_return_results(state: AgenticSearchState) -> str:
    """Handle a return_results_to_user tool call. Sets should_finish and returns confirmation."""
    state.should_finish = True
    count = len(state.marked_entity_ids)
    if count > 0:
        return f"Returning {count} marked results to the user."
    else:
        return "Returning with no results. Nothing will be shown to the user."


def _build_review(
    state: AgenticSearchState,
    messages: list[dict],
    context_window_tokens: int,
) -> str:
    """Build a review summary of marked results for the agent."""
    marked = state.marked_entity_ids
    results: list[AgenticSearchResult] = [
        state.results[eid] for eid in marked if eid in state.results
    ]

    if results:
        available = _estimate_available_tokens(messages, context_window_tokens)
        formatted = format_results_for_context(results, available)
        return (
            f"## Review: {len(results)} results marked\n\n"
            f"The following results will be returned to the user:\n\n"
            f"{formatted}\n\n"
            f"Call return_results_to_user to return these, or continue searching."
        )
    else:
        seen = len(state.results)
        return (
            f"## Review: 0 results marked\n\n"
            f"You have seen {seen} results but marked none as relevant.\n"
            f"Nothing will be returned to the user.\n\n"
            f"Call return_results_to_user to confirm, or continue searching and "
            f"mark relevant results."
        )
