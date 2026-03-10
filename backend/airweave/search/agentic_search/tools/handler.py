"""Tool call dispatcher for the agentic search agent."""

from airweave.search.agentic_search.emitter import AgenticSearchEmitter
from airweave.search.agentic_search.external.llm.tool_response import LLMToolCall
from airweave.search.agentic_search.schemas.state import AgenticSearchState
from airweave.search.agentic_search.services import AgenticSearchServices
from airweave.search.agentic_search.tools.count import handle_count
from airweave.search.agentic_search.tools.finish import (
    handle_return_results,
    handle_review_marked_results,
)
from airweave.search.agentic_search.tools.mark_as_relevant import handle_mark_as_relevant
from airweave.search.agentic_search.tools.read_previous_results import (
    handle_read_previous_results,
)
from airweave.search.agentic_search.tools.search import handle_search
from airweave.search.agentic_search.tools.unmark import handle_unmark


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
    if tc.name == "count":
        return await handle_count(
            tc=tc,
            services=services,
            collection_id=collection_id,
            user_filter=user_filter,
        )
    if tc.name == "read_previous_results":
        return await handle_read_previous_results(tc=tc, state=state)
    if tc.name == "mark_as_relevant":
        return await handle_mark_as_relevant(tc=tc, state=state)
    if tc.name == "unmark":
        return await handle_unmark(tc=tc, state=state)
    if tc.name == "review_marked_results":
        return handle_review_marked_results(state, state.messages, context_window_tokens)
    if tc.name == "return_results_to_user":
        return handle_return_results(state)
    raise ValueError(f"Unknown tool: {tc.name}")
