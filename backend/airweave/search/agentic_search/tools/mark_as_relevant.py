"""Mark as relevant tool: definition and handler.

Allows the agent to mark specific search results as relevant to the query.
After the loop ends, only marked results are reranked and returned.
"""

from typing import Any

from airweave.search.agentic_search.external.llm.tool_response import LLMToolCall
from airweave.search.agentic_search.schemas.state import AgenticSearchState

# ── Tool definition (sent to the LLM) ────────────────────────────────

MARK_AS_RELEVANT_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "mark_as_relevant",
        "description": (
            "Mark search results as relevant to the user's query. "
            "Only marked results will be returned to the user. "
            "You can call this multiple times to accumulate marked results."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Entity IDs of results to mark as relevant.",
                },
            },
            "required": ["entity_ids"],
        },
    },
}


# ── Handler ───────────────────────────────────────────────────────────


async def handle_mark_as_relevant(
    tc: LLMToolCall,
    state: AgenticSearchState,
) -> str:
    """Mark entity IDs as relevant in state and return confirmation."""
    entity_ids: list[str] = tc.arguments.get("entity_ids", [])
    if not entity_ids:
        return "No entity IDs provided."

    newly_marked, already_marked, not_found = state.mark_as_relevant(entity_ids)

    parts: list[str] = []
    if newly_marked:
        parts.append(f"Marked {len(newly_marked)} result(s) as relevant: {', '.join(newly_marked)}")
    if already_marked:
        parts.append(f"Already marked: {', '.join(already_marked)}")
    if not_found:
        parts.append(f"Not found in results: {', '.join(not_found)}")
    parts.append(f"Total marked results: {len(state.marked_entity_ids)}")

    return "\n".join(parts)
