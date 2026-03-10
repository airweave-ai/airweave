"""Count tool: definition and handler.

Allows the agent to count entities matching filters without retrieving content.
Useful for understanding data scale before committing to a search strategy.
"""

from typing import Any, List

from pydantic import BaseModel, Field

from airweave.search.agentic_search.external.llm.tool_response import LLMToolCall
from airweave.search.agentic_search.schemas.filter import AgenticSearchFilterGroup
from airweave.search.agentic_search.services import AgenticSearchServices

# ── Input schema ─────────────────────────────────────────────────────


class AgenticSearchCountParams(BaseModel):
    """Input schema for the count tool."""

    filter_groups: List[AgenticSearchFilterGroup] = Field(
        ...,
        description=(
            "Filter groups to count matching entities. "
            "Conditions within a group are combined with AND. "
            "Multiple groups are combined with OR."
        ),
    )


# ── Tool definition (sent to the LLM) ────────────────────────────────

COUNT_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "count",
        "description": (
            "Count entities matching filters without retrieving content. "
            "Use this to understand the scale of data before searching — "
            "e.g., how many entities exist in a source, of a certain type, "
            "or within a time range. No query needed — purely filter-based."
        ),
        "parameters": AgenticSearchCountParams.model_json_schema(),
    },
}


# ── Handler ───────────────────────────────────────────────────────────


async def handle_count(
    tc: LLMToolCall,
    services: AgenticSearchServices,
    collection_id: str,
    user_filter: list,
) -> str:
    """Count matching entities and return formatted result."""
    params = AgenticSearchCountParams.model_validate(tc.arguments)

    # Merge agent filters with user-supplied deterministic filters
    combined_filters = list(params.filter_groups) + list(user_filter)

    count = await services.vector_db.count(
        filter_groups=combined_filters,
        collection_id=collection_id,
    )

    if count == 0:
        return "No entities match these filters."
    return f"{count} entities match these filters."
