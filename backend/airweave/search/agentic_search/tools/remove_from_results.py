"""Remove from results tool: definition and handler.

Allows the agent to remove previously collected results from the result set.
"""

from typing import Any

from airweave.search.agentic_search.external.llm.tool_response import LLMToolCall
from airweave.search.agentic_search.schemas.state import AgenticSearchState

# ── Tool definition (sent to the LLM) ────────────────────────────────

REMOVE_FROM_RESULTS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "remove_from_results",
        "description": (
            "Remove entities from your result set. Use this when you realize "
            "collected results don't actually match the query. "
            "Pass 'all' as the only entity ID to clear everything."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Entity IDs to remove from the result set. "
                        "Pass ['all'] to clear all results."
                    ),
                },
            },
            "required": ["entity_ids"],
        },
    },
}


# ── Handler ───────────────────────────────────────────────────────────


async def handle_remove_from_results(
    tc: LLMToolCall,
    state: AgenticSearchState,
) -> str:
    """Remove entity IDs from the result set and return confirmation."""
    entity_ids: list[str] = tc.arguments.get("entity_ids", [])
    if not entity_ids:
        return "No entity IDs provided."

    # Support "all" shorthand
    if entity_ids == ["all"]:
        count = len(state.result_entity_ids)
        state.result_entity_ids.clear()
        return f"Removed all {count} result(s). Total results collected: 0"

    removed: list[str] = []
    not_in_results: list[str] = []
    for eid in entity_ids:
        if eid in state.result_entity_ids:
            state.result_entity_ids.discard(eid)
            removed.append(eid)
        else:
            not_in_results.append(eid)

    parts: list[str] = []
    if removed:
        parts.append(f"Removed {len(removed)} result(s): {', '.join(removed)}")
    if not_in_results:
        parts.append(f"Not in result set: {', '.join(not_in_results)}")
    parts.append(f"Total results collected: {len(state.result_entity_ids)}")

    return "\n".join(parts)
