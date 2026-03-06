"""Context management for the agentic search conversation loop.

Two-layer defense against context overflow:

Layer 1: Result truncation per tool response (in tools.py — format_results_for_context)
         Each tool result is capped at MAX_TOOL_RESULT_CONTEXT_SHARE of the context window.

Layer 2: Summarize old search results (this module — summarize_old_search_results)
         After each LLM call, replace search tool results the model has already seen
         with compact metadata summaries. Other tool results (e.g. read_previous_results)
         are kept intact. The model's reasoning is preserved in assistant messages.
"""

import copy

from airweave.search.agentic_search.schemas.search_result import AgenticSearchResult


def summarize_old_search_results(
    messages: list[dict],
    results_by_tool_call_id: dict[str, list[AgenticSearchResult]],
) -> list[dict]:
    """Replace search tool result messages with compact metadata summaries.

    Only summarizes tool results tagged with _tool_name="search".
    Other tool results (e.g. read_previous_results) are kept intact.
    """
    search_indices = [
        i
        for i, m in enumerate(messages)
        if m.get("role") == "tool" and m.get("_tool_name") == "search"
    ]
    if not search_indices:
        return messages

    messages = copy.copy(messages)

    for idx in search_indices:
        msg = messages[idx]
        tool_call_id = msg.get("tool_call_id", "")
        results = results_by_tool_call_id.get(tool_call_id)

        if results is None:
            continue

        summary = _format_summary(results)
        if msg.get("content") != summary:
            messages[idx] = {**msg, "content": summary}

    return messages


def _format_summary(results: list[AgenticSearchResult]) -> str:
    """Format results as compact metadata summaries."""
    if not results:
        return "No results found."
    header = f"**{len(results)} results** (metadata only, content omitted):\n\n"
    return header + "\n".join(r.to_summary_md() for r in results)
