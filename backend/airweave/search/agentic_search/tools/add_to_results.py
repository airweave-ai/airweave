"""Add to results tool: definition and handler.

Allows the agent to add search results to the result set that will be
returned to the user. Only results in the result set are returned.
"""

from typing import Any

from airweave.search.agentic_search.external.llm.tool_response import LLMToolCall
from airweave.search.agentic_search.schemas.state import AgenticSearchState

# ── Tool definition (sent to the LLM) ────────────────────────────────

ADD_TO_RESULTS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "add_to_results",
        "description": (
            "Add entities to the result set you're building for the user. "
            "Think of this as including results on a search results page — "
            "include everything the user would want to see. "
            "The cost of including a borderline result is low (the user scrolls past it). "
            "The cost of missing a matching result is high (the user never finds it). "
            "You can call this multiple times; results accumulate."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Entity IDs to add to the result set.",
                },
            },
            "required": ["entity_ids"],
        },
    },
}


# ── Handler ───────────────────────────────────────────────────────────


async def handle_add_to_results(
    tc: LLMToolCall,
    state: AgenticSearchState,
) -> str:
    """Add entity IDs to the result set and return confirmation."""
    entity_ids: list[str] = tc.arguments.get("entity_ids", [])
    if not entity_ids:
        return "No entity IDs provided."

    newly_added, already_added, not_found = state.add_to_results(entity_ids)

    parts: list[str] = []
    if newly_added:
        parts.append(f"Added {len(newly_added)} result(s): {', '.join(newly_added)}")
    if already_added:
        parts.append(f"Already in result set: {', '.join(already_added)}")
    if not_found:
        parts.append(f"Not found in search results: {', '.join(not_found)}")
    parts.append(f"Total results collected: {len(state.result_entity_ids)}")

    return "\n".join(parts)
