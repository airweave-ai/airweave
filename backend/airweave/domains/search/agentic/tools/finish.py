"""Finish tools — review collected results and end the search."""

from __future__ import annotations

from typing import Any

from airweave.domains.search.agentic.state import AgentState
from airweave.domains.search.agentic.tools.types import (
    FinishToolResult,
    RenderedResult,
    ReviewToolResult,
)

REVIEW_RESULTS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "review_results",
        "description": (
            "Review what you have collected so far. Shows all collected results "
            "so you can verify before returning. "
            "Does not end the search — you can continue after reviewing."
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


class ReviewResultsTool:
    """Show all collected results — full content for verification."""

    async def execute(
        self,
        arguments: dict[str, Any],
        state: AgentState,
        tool_call_id: str = "",
    ) -> ReviewToolResult:
        """Return all collected results rendered as full content."""
        entities = []
        for eid in state.collected_ids:
            result = state.results.get(eid)
            if result:
                entities.append(RenderedResult(entity_id=result.entity_id, text=result.to_md()))
        return ReviewToolResult(
            entities=entities,
            total_collected=len(state.collected_ids),
        )


class ReturnResultsTool:
    """End the search and return results to the user."""

    async def execute(
        self,
        arguments: dict[str, Any],
        state: AgentState,
        tool_call_id: str = "",
    ) -> FinishToolResult:
        """Signal the agent loop to stop.

        Soft-gates if very few results collected relative to many seen,
        giving the agent one chance to reconsider.
        """
        collected_count = len(state.collected_ids)
        seen_count = len(state.results)

        if collected_count < 20 and seen_count > 100 and not state.return_warned:
            state.return_warned = True
            return FinishToolResult(
                accepted=False,
                warning=(
                    f"You are about to return only {collected_count} results "
                    f"but have seen {seen_count} entities. "
                    "Consider collecting more or searching differently."
                ),
                total_collected=collected_count,
            )

        state.should_finish = True
        return FinishToolResult(accepted=True, total_collected=collected_count)
