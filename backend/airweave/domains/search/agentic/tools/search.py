"""Search tool — query the vector database for relevant entities.

Uses the shared SearchPlanExecutor to embed, compile, and execute.
Returns summaries (via to_snippet_summary_md) — the context manager
decides how many fit in the window.
"""

from __future__ import annotations

from typing import Any

from airweave.domains.search.agentic.state import AgentState
from airweave.domains.search.agentic.tools.types import RenderedResult, SearchToolResult
from airweave.domains.search.protocols import SearchPlanExecutorProtocol
from airweave.domains.search.types import FilterGroup, SearchPlan

SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search",
        "description": (
            "Search the vector database for relevant entities. "
            "Use different queries, expansions, retrieval strategies "
            "(semantic, keyword, hybrid), limits and filters to refine results."
        ),
        "parameters": SearchPlan.model_json_schema(),
    },
}


class SearchTool:
    """Validates LLM args as a SearchPlan and executes via the shared executor."""

    def __init__(
        self,
        executor: SearchPlanExecutorProtocol,
        user_filter: list[FilterGroup],
        collection_id: str,
    ) -> None:
        """Initialize with executor, user filter, and collection ID."""
        self._executor = executor
        self._user_filter = user_filter
        self._collection_id = collection_id

    async def execute(
        self,
        arguments: dict[str, Any],
        state: AgentState,
        tool_call_id: str = "",
    ) -> SearchToolResult:
        """Execute search. ValidationError on bad args is caught by dispatcher."""
        plan = SearchPlan.model_validate(arguments)
        results = await self._executor.execute(
            plan=plan,
            user_filter=self._user_filter,
            collection_id=self._collection_id,
        )

        # Track new results in state
        new_count = 0
        for r in results.results:
            if r.entity_id not in state.results:
                state.results[r.entity_id] = r
                new_count += 1

        if tool_call_id:
            state.results_by_tool_call_id[tool_call_id] = results.results

        # Render as summaries
        summaries = [
            RenderedResult(entity_id=r.entity_id, text=r.to_snippet_summary_md())
            for r in results.results
        ]

        return SearchToolResult(
            summaries=summaries,
            new_count=new_count,
            requested_limit=plan.limit,
            requested_offset=plan.offset,
        )
