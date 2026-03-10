"""Context management for the agentic search conversation loop.

Three-tier context retention for both search and read tool results:

| Tier     | Search results              | Read results                    |
|----------|-----------------------------|---------------------------------|
| Current  | Full snippet summaries      | Full content                    |
| Previous | ID + name list only         | Metadata summaries (to_summary) |
| Older    | One-line digest             | One-line digest                 |

The agent loop tracks rolling windows of {current, previous} tool call IDs
for both search and read. Each iteration:
- Current becomes previous
- Previous becomes older (gets digested)
"""

import copy

from airweave.search.agentic_search.schemas.search_result import AgenticSearchResult


def manage_context(
    messages: list[dict],
    results_by_tool_call_id: dict[str, list[AgenticSearchResult]],
    reads_by_tool_call_id: dict[str, list[AgenticSearchResult]],
    current_search_ids: set[str],
    current_read_ids: set[str],
    previous_search_ids: set[str],
    previous_read_ids: set[str],
) -> list[dict]:
    """Apply 3-tier context retention to search and read tool results.

    Current iteration results: kept as-is (full content).
    Previous iteration results: summarized to metadata.
    Older results (2+ iterations ago): digested to one-line counts.
    """
    all_current = current_search_ids | current_read_ids
    all_previous = previous_search_ids | previous_read_ids

    # Find tool result messages that need processing
    needs_update = False
    for m in messages:
        if m.get("role") != "tool":
            continue
        tc_id = m.get("tool_call_id", "")
        tool_name = m.get("_tool_name", "")
        if tool_name not in ("search", "read"):
            continue
        if tc_id in all_current:
            continue
        # This message is either previous or older — needs summarization
        needs_update = True
        break

    if not needs_update:
        return messages

    messages = copy.copy(messages)

    for idx, msg in enumerate(messages):
        if msg.get("role") != "tool":
            continue

        tc_id = msg.get("tool_call_id", "")
        tool_name = msg.get("_tool_name", "")

        if tool_name not in ("search", "read"):
            continue

        # Skip current iteration — keep full content
        if tc_id in all_current:
            continue

        if tool_name == "search":
            results = results_by_tool_call_id.get(tc_id)
            if results is None:
                continue

            if tc_id in previous_search_ids:
                # Previous: ID + name list only
                summary = _format_search_previous(results)
            else:
                # Older: one-line digest
                summary = _format_search_older(results)

            if msg.get("content") != summary:
                messages[idx] = {**msg, "content": summary}

        elif tool_name == "read":
            results = reads_by_tool_call_id.get(tc_id)
            if results is None:
                continue

            if tc_id in previous_read_ids:
                # Previous: metadata summaries
                summary = _format_read_previous(results)
            else:
                # Older: one-line digest
                summary = _format_read_older(results)

            if msg.get("content") != summary:
                messages[idx] = {**msg, "content": summary}

    return messages


# ── Kept for backwards compat (used by tests, finish.py review) ──────


def summarize_old_search_results(
    messages: list[dict],
    results_by_tool_call_id: dict[str, list[AgenticSearchResult]],
    skip_tool_call_ids: set[str] | None = None,
) -> list[dict]:
    """Legacy summarizer — delegates to manage_context with simple tier mapping.

    Treats skip_tool_call_ids as current, everything else as older.
    """
    current = skip_tool_call_ids or set()
    return manage_context(
        messages=messages,
        results_by_tool_call_id=results_by_tool_call_id,
        reads_by_tool_call_id={},
        current_search_ids=current,
        current_read_ids=set(),
        previous_search_ids=set(),
        previous_read_ids=set(),
    )


# ── Formatters ────────────────────────────────────────────────────────


def _format_search_previous(results: list[AgenticSearchResult]) -> str:
    """Previous-tier search: ID + name list only."""
    if not results:
        return "No results found."
    lines = [f"**{len(results)} search results** (IDs only — use `read` for content):\n"]
    for r in results:
        lines.append(f"- `{r.entity_id}`: {r.name} (score: {r.relevance_score:.4f})")
    return "\n".join(lines)


def _format_search_older(results: list[AgenticSearchResult]) -> str:
    """Older-tier search: one-line digest."""
    if not results:
        return "No results found."
    return f"*[Searched: {len(results)} results returned]*"


def _format_read_previous(results: list[AgenticSearchResult]) -> str:
    """Previous-tier read: metadata summaries."""
    if not results:
        return "*[Read: no results]*"
    # Deduplicate by original_entity_id for cleaner output
    seen_originals: set[str] = set()
    unique_results: list[AgenticSearchResult] = []
    for r in results:
        orig_id = r.airweave_system_metadata.original_entity_id
        if orig_id not in seen_originals:
            seen_originals.add(orig_id)
            unique_results.append(r)

    header = f"**Read {len(unique_results)} entities** (metadata only, content omitted):\n\n"
    return header + "\n".join(r.to_summary_md() for r in unique_results)


def _format_read_older(results: list[AgenticSearchResult]) -> str:
    """Older-tier read: one-line digest."""
    if not results:
        return "*[Read: no results]*"
    # Count unique original entities
    unique = len({r.airweave_system_metadata.original_entity_id for r in results})
    return f"*[Read {unique} entities]*"
