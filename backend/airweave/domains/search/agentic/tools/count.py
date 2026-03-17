"""Count tool — count entities matching filters without retrieval."""

from __future__ import annotations

from typing import Any

from airweave.domains.search.adapters.vector_db.protocol import VectorDBProtocol
from airweave.domains.search.agentic.state import AgentState
from airweave.domains.search.agentic.tools.types import CountToolResult
from airweave.domains.search.types.filters import FilterGroup

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
        "parameters": {
            "type": "object",
            "properties": {
                "filter_groups": {
                    "type": "array",
                    "items": FilterGroup.model_json_schema(),
                    "description": (
                        "Filter groups to narrow the count. "
                        "Conditions within a group are AND. "
                        "Multiple groups are OR."
                    ),
                },
            },
            "required": ["filter_groups"],
        },
    },
}


class CountTool:
    """Count entities matching filters without retrieving content."""

    def __init__(
        self,
        vector_db: VectorDBProtocol,
        collection_id: str,
        user_filter: list[FilterGroup],
    ) -> None:
        """Initialize with vector DB, collection ID, and user filter."""
        self._vector_db = vector_db
        self._collection_id = collection_id
        self._user_filter = user_filter

    async def execute(
        self,
        arguments: dict[str, Any],
        state: AgentState,
        tool_call_id: str = "",
    ) -> CountToolResult:
        """Count matching entities. ValidationError on bad filters caught by dispatcher."""
        raw_groups = arguments.get("filter_groups", [])
        validated = [FilterGroup.model_validate(fg) for fg in raw_groups]
        combined = validated + self._user_filter

        count = await self._vector_db.count(combined, self._collection_id)
        return CountToolResult(count=count)
