"""Unmark tool: definition and handler.

Allows the agent to remove previously marked results.
"""

from typing import Any

from airweave.search.agentic_search.external.llm.tool_response import LLMToolCall
from airweave.search.agentic_search.schemas.state import AgenticSearchState

# ── Tool definition (sent to the LLM) ────────────────────────────────

UNMARK_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "unmark",
        "description": (
            "Remove previously marked results. Use this when you realize "
            "marked results are not actually relevant to the query. "
            "Pass 'all' as the only entity ID to unmark everything."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Entity IDs to unmark. "
                        "Pass ['all'] to unmark all results."
                    ),
                },
            },
            "required": ["entity_ids"],
        },
    },
}


# ── Handler ───────────────────────────────────────────────────────────


async def handle_unmark(
    tc: LLMToolCall,
    state: AgenticSearchState,
) -> str:
    """Remove entity IDs from marked set and return confirmation."""
    entity_ids: list[str] = tc.arguments.get("entity_ids", [])
    if not entity_ids:
        return "No entity IDs provided."

    # Support "all" shorthand
    if entity_ids == ["all"]:
        count = len(state.marked_entity_ids)
        state.marked_entity_ids.clear()
        return f"Unmarked all {count} result(s). Total marked results: 0"

    removed: list[str] = []
    not_marked: list[str] = []
    for eid in entity_ids:
        if eid in state.marked_entity_ids:
            state.marked_entity_ids.discard(eid)
            removed.append(eid)
        else:
            not_marked.append(eid)

    parts: list[str] = []
    if removed:
        parts.append(f"Unmarked {len(removed)} result(s): {', '.join(removed)}")
    if not_marked:
        parts.append(f"Not currently marked: {', '.join(not_marked)}")
    parts.append(f"Total marked results: {len(state.marked_entity_ids)}")

    return "\n".join(parts)
