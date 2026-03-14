"""Review and return tools for the agentic search agent.

Two separate tools:
- review_results: Shows what's currently collected. Optional, non-terminal.
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

REVIEW_RESULTS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "review_results",
        "description": (
            "Review what you have collected so far. Shows all collected results with "
            "their full content so you can verify before returning. "
            "Does not end the search — you can continue searching, collecting, or "
            "removing after reviewing."
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
            "Return your collected result set to the user and end the search. "
            "This is final — the search loop ends immediately. "
            "You can call add_to_results and return_results_to_user "
            "in the same response."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}


# ── Handlers ─────────────────────────────────────────────────────────


def handle_review_results(
    state: AgenticSearchState,
    messages: list[dict],
    context_window_tokens: int,
) -> str:
    """Handle a review_results tool call. Returns review text."""
    return _build_review(state, messages, context_window_tokens)


def handle_return_results(state: AgenticSearchState) -> str:
    """Handle a return_results_to_user tool call.

    Includes a soft return-gate: if the agent has seen many results but
    collected very few, warn once before allowing the return.
    """
    count = len(state.result_entity_ids)
    seen = len(state.results)

    # Soft gate: warn if returning very few results relative to what was seen
    if count < 20 and seen > 50 and not state.return_warned:
        state.return_warned = True
        return (
            f"You are about to return only {count} results, but you have seen "
            f"{seen} entities. A basic vector search would return more results "
            f"than this. Are you sure you've collected everything that matches? "
            f"Consider re-reading results you may have skipped and adding more. "
            f"Call return_results_to_user again to confirm."
        )

    state.should_finish = True
    if count > 0:
        return f"Returning {count} results to the user."
    else:
        return "Returning with no results. Nothing will be shown to the user."


def _build_review(
    state: AgenticSearchState,
    messages: list[dict],
    context_window_tokens: int,
) -> str:
    """Build a review summary of collected results for the agent."""
    collected = state.result_entity_ids
    results: list[AgenticSearchResult] = [
        state.results[eid] for eid in collected if eid in state.results
    ]

    if results:
        available = _estimate_available_tokens(messages, context_window_tokens)
        formatted = format_results_for_context(results, available)
        return (
            f"## Review: {len(results)} results collected\n\n"
            f"The following results will be returned to the user:\n\n"
            f"{formatted}\n\n"
            f"Call return_results_to_user to return these, or continue searching."
        )
    else:
        seen = len(state.results)
        return (
            f"## Review: 0 results collected\n\n"
            f"You have seen {seen} results but collected none.\n"
            f"Nothing will be returned to the user.\n\n"
            f"Call return_results_to_user to confirm, or continue searching and "
            f"add matching results with add_to_results."
        )
