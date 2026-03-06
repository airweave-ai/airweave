"""Read previous results tool: definition and handler.

Allows the agent to retrieve the full content of previously seen search results
by entity ID. Useful when old tool results have been summarized and the agent
needs to re-examine specific results.
"""

from typing import Any

from airweave.search.agentic_search.external.llm.tool_response import LLMToolCall
from airweave.search.agentic_search.schemas.state import AgenticSearchState

# ── Tool definition (sent to the LLM) ────────────────────────────────

READ_PREVIOUS_RESULTS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "read_previous_results",
        "description": (
            "Retrieve the full content of previously seen search results by entity ID. "
            "Use this when you need to re-examine results that have been summarized "
            "from earlier search iterations."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Entity IDs to retrieve full content for.",
                },
            },
            "required": ["entity_ids"],
        },
    },
}


# ── Handler ───────────────────────────────────────────────────────────


async def handle_read_previous_results(
    tc: LLMToolCall,
    state: AgenticSearchState,
) -> str:
    """Look up previously seen results by entity ID and return their full content."""
    entity_ids: list[str] = tc.arguments.get("entity_ids", [])

    found = []
    not_found = []
    for entity_id in entity_ids:
        result = state.results.get(entity_id)
        if result:
            found.append(result)
        else:
            not_found.append(entity_id)

    parts: list[str] = []
    if found:
        parts.append(f"**{len(found)} of {len(entity_ids)} results retrieved:**\n")
        parts.append("\n\n---\n\n".join(r.to_md() for r in found))
    if not_found:
        parts.append(f"**Not found:** {', '.join(not_found)}")
    if not parts:
        return "No entity IDs provided."

    return "\n\n".join(parts)
