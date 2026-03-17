"""Context management for the agentic search agent.

Three responsibilities:
1. compress_history — 3-tier retention of old tool result messages
2. fit_tool_result — truncate current tool results to fit available budget
3. check_budget — safety valve when context is dangerously full

Token counting always uses the tokenizer (never chars/4).
Context window = input + output combined (all providers).
Input budget = context_window - output_reserve.

Only tool result messages are managed. The model's own assistant messages
(thinking + tool calls) are NEVER truncated.
"""

from __future__ import annotations

import json
from typing import Union

from airweave.core.protocols.tokenizer import TokenizerProtocol
from airweave.domains.search.agentic.state import AgentState
from airweave.domains.search.agentic.tools.types import (
    COMPRESSIBLE_TOOLS,
    READ_LIKE_TOOLS,
    SEARCH_LIKE_TOOLS,
    CollectToolResult,
    CountToolResult,
    FinishToolResult,
    NavigateToolResult,
    ReadToolResult,
    ReviewToolResult,
    SearchToolResult,
    ToolErrorResult,
    ToolName,
)
from airweave.domains.search.config import SearchConfig
from airweave.domains.search.types.results import SearchResult

ToolResult = Union[
    SearchToolResult,
    ReadToolResult,
    CollectToolResult,
    CountToolResult,
    NavigateToolResult,
    ReviewToolResult,
    FinishToolResult,
    ToolErrorResult,
]


# Reserve tokens for system nudges appended after tool results
# (iteration warnings, stagnation nudges, progress messages)
_NUDGE_RESERVE_TOKENS = 500


class ContextManager:
    """Manages the LLM context window for the agentic search agent."""

    def __init__(
        self,
        tokenizer: TokenizerProtocol,
        context_window: int,
        max_output_tokens: int,
        thinking_enabled: bool,
        system_prompt: str,
        tools: list[dict],
    ) -> None:
        """Initialize with model constraints and fixed request data.

        Args:
            tokenizer: For accurate token counting.
            context_window: Model's total context window (input + output).
            max_output_tokens: Model's max output token limit.
            thinking_enabled: Whether thinking/reasoning is enabled.
            system_prompt: The full system prompt (fixed per request).
            tools: Tool definitions sent to the LLM (fixed per request).
        """
        self._tokenizer = tokenizer
        self._context_window = context_window
        self._max_output_tokens = max_output_tokens
        self._thinking_enabled = thinking_enabled

        # Cache fixed overhead (doesn't change per request)
        self._system_prompt_tokens = tokenizer.count_tokens(system_prompt)
        self._tools_tokens = tokenizer.count_tokens(json.dumps(tools))

    # ── Budget calculation ────────────────────────────────────────────

    @property
    def output_reserve(self) -> int:
        """Tokens reserved for the model's response (thinking + tool calls)."""
        if self._thinking_enabled:
            return int(self._max_output_tokens * 0.75)
        return SearchConfig.NON_THINKING_OUTPUT_RESERVE

    @property
    def input_budget(self) -> int:
        """Max tokens available for input (system + tools + messages)."""
        return self._context_window - self.output_reserve

    @property
    def fixed_overhead(self) -> int:
        """Tokens used by system prompt + tool definitions (constant)."""
        return self._system_prompt_tokens + self._tools_tokens

    def available_budget(self, messages: list[dict]) -> int:
        """Calculate remaining token budget for new content.

        Accounts for fixed overhead (system prompt + tools), all current
        messages, and a reserve for system nudges (iteration warnings,
        stagnation, progress).
        """
        used = self.fixed_overhead + self._count_messages_tokens(messages)
        return max(0, self.input_budget - used - _NUDGE_RESERVE_TOKENS)

    # ── 1. Compress history ───────────────────────────────────────────

    def compress_history(
        self,
        messages: list[dict],
        state: AgentState,
        current_search_ids: set[str],
        current_read_ids: set[str],
        previous_search_ids: set[str],
        previous_read_ids: set[str],
    ) -> list[dict]:
        """Apply 3-tier compression to old tool result messages.

        Current iteration: untouched (full summaries/content)
        Previous iteration: search → ID+name list, read → metadata summaries
        Older: one-line digest

        Returns a new message list (does not mutate input).
        """
        all_current = current_search_ids | current_read_ids

        # Quick check: anything to compress?
        has_compressible = any(
            m.get("role") == "tool"
            and m.get("_tool_name", "") in COMPRESSIBLE_TOOLS
            and m.get("tool_call_id", "") not in all_current
            for m in messages
        )
        if not has_compressible:
            return messages

        result = list(messages)
        for idx, msg in enumerate(result):
            compressed = self._compress_message(
                msg, state, all_current, previous_search_ids, previous_read_ids
            )
            if compressed is not None:
                result[idx] = compressed

        return result

    def _compress_message(
        self,
        msg: dict,
        state: AgentState,
        all_current: set[str],
        previous_search_ids: set[str],
        previous_read_ids: set[str],
    ) -> dict | None:
        """Compress a single tool result message. Returns new dict or None if unchanged."""
        if msg.get("role") != "tool":
            return None

        tc_id = msg.get("tool_call_id", "")
        tool_name = msg.get("_tool_name", "")

        if tool_name not in COMPRESSIBLE_TOOLS or tc_id in all_current:
            return None

        if tool_name in SEARCH_LIKE_TOOLS:
            results = state.results_by_tool_call_id.get(tc_id)
            if results is None:
                return None
            summary = (
                _format_search_previous(results)
                if tc_id in previous_search_ids
                else _format_search_older(results)
            )
        elif tool_name in READ_LIKE_TOOLS:
            # review_results shows collected entities — compress like reads
            results = state.reads_by_tool_call_id.get(tc_id)
            if results is None:
                # review_results doesn't store in reads_by_tool_call_id,
                # so fall back to collecting from state
                if tool_name == ToolName.REVIEW_RESULTS:
                    results = [
                        state.results[eid] for eid in state.collected_ids if eid in state.results
                    ]
                else:
                    return None
            summary = (
                _format_read_previous(results)
                if tc_id in previous_read_ids
                else _format_read_older(results)
            )
        else:
            return None

        if msg.get("content") == summary:
            return None
        return {**msg, "content": summary}

    # ── 2. Fit tool result ────────────────────────────────────────────

    def fit_tool_result(
        self,
        result: ToolResult,
        messages: list[dict],
    ) -> str:
        """Fit a tool result into the available context budget.

        For results with lists of rendered items (search summaries, read
        entities), drops items from the bottom until they fit. Small results
        (collect, count, finish, error) always fit.

        Returns the content string for the tool result message.
        """
        available = self.available_budget(messages)

        if isinstance(result, SearchToolResult):
            return self._fit_search_result(result, available)
        if isinstance(result, NavigateToolResult):
            return self._fit_navigate_result(result, available)
        if isinstance(result, (ReadToolResult, ReviewToolResult)):
            return self._fit_read_result(result, available)
        if isinstance(result, CollectToolResult):
            return _format_collect_result(result)
        if isinstance(result, CountToolResult):
            return _format_count_result(result)
        if isinstance(result, FinishToolResult):
            return _format_finish_result(result)
        if isinstance(result, ToolErrorResult):
            return f"Error: {result.error}"

        return str(result)

    def _fit_search_result(self, result: SearchToolResult, available_tokens: int) -> str:
        """Fit search summaries into budget, dropping from bottom."""
        if not result.summaries:
            return "No results found."

        header = f"**{len(result.summaries)} results** ({result.new_count} new):\n\n"
        header_tokens = self._tokenizer.count_tokens(header)
        remaining = available_tokens - header_tokens

        included = []
        for summary in result.summaries:
            tokens = self._tokenizer.count_tokens(summary.text)
            if remaining - tokens < 0 and included:
                break
            included.append(summary.text)
            remaining -= tokens

        truncated = len(result.summaries) - len(included)
        parts = [header] + included
        if truncated > 0:
            parts.append(f"\n\n*({truncated} more results not shown — context budget)*")

        # Pagination warning: tell agent more results exist
        if result.requested_limit > 0 and len(result.summaries) >= result.requested_limit:
            next_offset = result.requested_offset + result.requested_limit
            parts.append(
                f"\n\n**Results hit the limit of {result.requested_limit}.** "
                f"More results likely exist. Use offset={next_offset} to see the next page."
            )

        return "\n\n".join(parts)

    def _fit_navigate_result(self, result: NavigateToolResult, available_tokens: int) -> str:
        """Fit navigation summaries into budget."""
        if not result.summaries:
            return f"No {result.context_label} found."

        header = f"**{len(result.summaries)} {result.context_label}:**\n\n"
        header_tokens = self._tokenizer.count_tokens(header)
        remaining = available_tokens - header_tokens

        included = []
        for summary in result.summaries:
            tokens = self._tokenizer.count_tokens(summary.text)
            if remaining - tokens < 0 and included:
                break
            included.append(summary.text)
            remaining -= tokens

        truncated = len(result.summaries) - len(included)
        parts = [header] + included
        if truncated > 0:
            parts.append(f"\n\n*({truncated} more results not shown — context budget)*")

        return "\n\n".join(parts)

    def _fit_read_result(
        self, result: ReadToolResult | ReviewToolResult, available_tokens: int
    ) -> str:
        """Fit read/review entities into budget, dropping from bottom."""
        if isinstance(result, ReadToolResult):
            entities = result.entities
            not_found = result.not_found
            total_label = f"**{len(entities)} entities read:**\n\n"
        else:
            entities = result.entities
            not_found = []
            total_label = f"**Review: {result.total_collected} results collected:**\n\n"

        if not entities and not not_found:
            return "No results."

        header_tokens = self._tokenizer.count_tokens(total_label)
        remaining = available_tokens - header_tokens

        included = []
        for entity in entities:
            tokens = self._tokenizer.count_tokens(entity.text)
            if remaining - tokens < 0 and included:
                break
            included.append(entity.text)
            remaining -= tokens

        truncated = len(entities) - len(included)
        parts = [total_label] + included

        if not_found:
            parts.append(f"\n\nNot found: {', '.join(not_found)}")

        if truncated > 0:
            parts.append(f"\n\n*({truncated} entities not shown — context budget)*")

        # Triage nudge for read results: remind agent to collect
        if isinstance(result, ReadToolResult) and result.read_entity_ids:
            id_list = ", ".join(f"`{eid}`" for eid in result.read_entity_ids[:20])
            parts.append(
                f"\n\n**Entities read:** [{id_list}]\n"
                "Add matching results to your result set now (`add_to_results`) "
                "— their content will be summarized after your next search."
            )

        return "\n\n".join(parts)

    # ── 3. Budget check (safety valve) ────────────────────────────────

    def check_budget(self, messages: list[dict]) -> bool:
        """Check if there's enough budget for useful work.

        Returns True if budget is healthy, False if dangerously low.
        The agent loop uses this to decide whether to trigger
        conversation summarization.
        """
        return self.available_budget(messages) >= SearchConfig.MIN_USEFUL_BUDGET_TOKENS

    # ── Token counting ────────────────────────────────────────────────

    def _count_messages_tokens(self, messages: list[dict]) -> int:
        """Count total tokens across all messages using the tokenizer."""
        total = 0
        for msg in messages:
            content = msg.get("content") or ""
            if isinstance(content, list):
                content = json.dumps(content)
            total += self._tokenizer.count_tokens(str(content))

            # Tool calls in assistant messages also consume tokens
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                total += self._tokenizer.count_tokens(json.dumps(tool_calls))

            # _thinking stored separately also consumes tokens
            thinking = msg.get("_thinking")
            if thinking:
                total += self._tokenizer.count_tokens(thinking)

        return total


# ── Compression formatters ────────────────────────────────────────────


def _format_search_previous(results: list[SearchResult]) -> str:
    """Previous-tier search: ID + name list only."""
    if not results:
        return "No results found."
    lines = [f"**{len(results)} search results** (IDs only — use `read` for content):\n"]
    for r in results:
        lines.append(f"- `{r.entity_id}`: {r.name} (score: {r.relevance_score:.4f})")
    return "\n".join(lines)


def _format_search_older(results: list[SearchResult]) -> str:
    """Older-tier search: one-line digest."""
    if not results:
        return "No results found."
    return f"*[Searched: {len(results)} results returned]*"


def _format_read_previous(results: list[SearchResult]) -> str:
    """Previous-tier read: metadata summaries."""
    if not results:
        return "*[Read: no results]*"
    seen_originals: set[str] = set()
    unique: list[SearchResult] = []
    for r in results:
        orig_id = r.airweave_system_metadata.original_entity_id
        if orig_id not in seen_originals:
            seen_originals.add(orig_id)
            unique.append(r)

    header = f"**Read {len(unique)} entities** (metadata only, content omitted):\n\n"
    return header + "\n".join(r.to_summary_md() for r in unique)


def _format_read_older(results: list[SearchResult]) -> str:
    """Older-tier read: one-line digest."""
    if not results:
        return "*[Read: no results]*"
    unique = len({r.airweave_system_metadata.original_entity_id for r in results})
    return f"*[Read {unique} entities]*"


# ── Small tool result formatters (always fit) ─────────────────────────


def _format_collect_result(result: CollectToolResult) -> str:
    """Format collect (add/remove) result."""
    parts = []
    if result.added:
        ids = ", ".join(result.added[:20])
        parts.append(f"Added {len(result.added)} result(s): {ids}")
    if result.removed:
        ids = ", ".join(result.removed[:20])
        parts.append(f"Removed {len(result.removed)} result(s): {ids}")
    if result.already_collected:
        ids = ", ".join(result.already_collected[:10])
        parts.append(f"Already collected: {ids}")
    if result.not_found:
        ids = ", ".join(result.not_found[:10])
        parts.append(f"Not found in search results: {ids}")
    parts.append(f"Total collected: {result.total_collected}")
    return "\n".join(parts)


def _format_count_result(result: CountToolResult) -> str:
    """Format count result."""
    if result.count == 0:
        return "No entities match these filters."
    return f"{result.count} entities match these filters."


def _format_finish_result(result: FinishToolResult) -> str:
    """Format finish result."""
    if not result.accepted and result.warning:
        return result.warning
    if result.total_collected == 0:
        return "Returning with no results."
    return f"Returning {result.total_collected} results to the user."
