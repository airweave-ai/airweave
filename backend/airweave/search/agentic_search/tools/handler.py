"""Tool call dispatcher for the agentic search agent."""

from airweave.search.agentic_search.emitter import AgenticSearchEmitter
from airweave.search.agentic_search.external.llm.tool_response import LLMToolCall
from airweave.search.agentic_search.schemas.state import AgenticSearchState
from airweave.search.agentic_search.services import AgenticSearchServices
from airweave.search.agentic_search.tools.mark_as_relevant import handle_mark_as_relevant
from airweave.search.agentic_search.tools.read_previous_results import (
    handle_read_previous_results,
)
from airweave.search.agentic_search.tools.search import handle_search


async def handle_tool_call(
    tc: LLMToolCall,
    state: AgenticSearchState,
    services: AgenticSearchServices,
    emitter: AgenticSearchEmitter,
    collection_id: str,
    user_filter: list,
    context_window_tokens: int,
) -> str:
    """Dispatch a tool call to the appropriate handler.

    Returns the formatted content string for the tool result message.
    """
    if tc.name == "search":
        return await handle_search(
            tc=tc,
            state=state,
            services=services,
            emitter=emitter,
            collection_id=collection_id,
            user_filter=user_filter,
            context_window_tokens=context_window_tokens,
        )
    if tc.name == "read_previous_results":
        return await handle_read_previous_results(tc=tc, state=state)
    if tc.name == "mark_as_relevant":
        return await handle_mark_as_relevant(tc=tc, state=state)
    raise ValueError(f"Unknown tool: {tc.name}")
