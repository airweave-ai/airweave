"""Finish tool: definition and handler for the agentic search agent.

Allows the agent to explicitly signal it is done searching, with a
review step that shows marked results before confirming.
"""

from typing import Any

from airweave.search.agentic_search.schemas.search_result import AgenticSearchResult
from airweave.search.agentic_search.schemas.state import AgenticSearchState
from airweave.search.agentic_search.tools.search import (
    _estimate_available_tokens,
    format_results_for_context,
)

# ── Tool definition (sent to the LLM) ────────────────────────────────

FINISH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "finish",
        "description": (
            "Call this tool when you are done searching. "
            "Shows a review of your marked results. "
            "Call again to confirm and return the results to the user. "
            "If you do anything else between calls (search, mark, etc.), "
            "you will need to review again. "
            "You can call mark_as_relevant and finish in the same response."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
}


# ── Handler ───────────────────────────────────────────────────────────


def handle_finish(
    state: AgenticSearchState,
    messages: list[dict],
    context_window_tokens: int,
) -> tuple[str, bool]:
    """Handle a finish tool call.

    Returns (content, should_end).
    """
    if state.awaiting_finish_confirmation:
        return ("Finishing search.", True)

    state.awaiting_finish_confirmation = True
    review = _build_review(state, messages, context_window_tokens)
    return (review, False)


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
            f"## Finish review: {len(results)} results marked\n\n"
            f"The following results will be returned to the user:\n\n"
            f"{formatted}\n\n"
            f"Call finish again to return these results, or continue searching."
        )
    else:
        seen = len(state.results)
        return (
            f"## Finish review: 0 results marked\n\n"
            f"You have seen {seen} results but marked none as relevant.\n"
            f"Nothing will be returned to the user.\n\n"
            f"Call finish again to confirm, or continue searching and "
            f"mark relevant results."
        )
