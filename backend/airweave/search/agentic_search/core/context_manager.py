"""Context management for the agentic search conversation loop.

Three-layer defense against context overflow (inspired by OpenClaw):

Layer 1: Result truncation per tool response (in tools.py — format_results_for_tool_response)
         Each tool result is capped at MAX_TOOL_RESULT_CONTEXT_SHARE of the context window.

Layer 2: Prune old tool results as conversation grows (this module — prune_context)
         Before each API call, compress old tool results while preserving
         the model's reasoning about them.

Layer 3: Compaction / overflow recovery (this module — compact_conversation)
         If the API returns a context overflow error despite pruning,
         summarize old conversation with a separate LLM call.

Key insight: The model's own text (reasoning between tool calls) is NEVER pruned.
Only raw tool results are trimmed. The model retains its analysis of what it saw.
"""

import copy
import logging

from airweave.core.logging import logger as _default_logger
from airweave.search.agentic_search.config import CHARS_PER_TOKEN

# ── Constants ──────────────────────────────────────────────────────────

# Layer 2 thresholds
SOFT_TRIM_RATIO = 0.6  # Start soft-trimming at 60% of context
HARD_CLEAR_RATIO = 0.8  # Start hard-clearing at 80% of context
KEEP_LAST_N_RESULTS = 1  # Always keep the most recent tool result intact

# Soft trim: keep head + tail of tool results
SOFT_TRIM_HEAD_CHARS = 2000
SOFT_TRIM_TAIL_CHARS = 500

HARD_CLEAR_PLACEHOLDER = "[Tool result cleared to free context space.]"

# ── Layer 2: Context pruning ──────────────────────────────────────────


def estimate_message_chars(message: dict) -> int:
    """Estimate the character count of a message."""
    content = message.get("content", "")
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        total = 0
        for block in content:
            if isinstance(block, dict):
                # Text blocks
                if block.get("type") == "text":
                    total += len(block.get("text", ""))
                # Tool result blocks
                elif block.get("type") == "tool_result":
                    c = block.get("content", "")
                    total += len(c) if isinstance(c, str) else 0
                # Tool use blocks (small)
                elif block.get("type") == "tool_use":
                    total += 200  # rough estimate for tool call metadata
            elif isinstance(block, str):
                total += len(block)
        return total
    return 0


def estimate_total_chars(messages: list[dict]) -> int:
    """Estimate total character count across all messages."""
    return sum(estimate_message_chars(m) for m in messages)


def _is_tool_result_message(message: dict) -> bool:
    """Check if a message is a tool result (works for both OpenAI and Anthropic formats)."""
    return message.get("role") == "tool"


def _find_tool_result_indices(messages: list[dict]) -> list[int]:
    """Find indices of tool result messages."""
    return [i for i, m in enumerate(messages) if _is_tool_result_message(m)]


def _soft_trim_content(content: str, head_chars: int, tail_chars: int) -> str:
    """Keep head and tail of content, replace middle with ellipsis."""
    if len(content) <= head_chars + tail_chars:
        return content

    head = content[:head_chars]
    tail = content[-tail_chars:] if tail_chars > 0 else ""
    trimmed_chars = len(content) - head_chars - tail_chars

    return f"{head}\n\n[... {trimmed_chars} characters trimmed ...]\n\n{tail}"


def prune_context(
    messages: list[dict],
    context_window_tokens: int,
    logger: logging.Logger | logging.LoggerAdapter | None = None,
) -> list[dict]:
    """Prune old tool results from the messages array.

    Only tool result messages are pruned. The model's own assistant messages
    (reasoning) are NEVER touched. This means the model retains its own
    analysis of what it saw, even after the raw data is removed.

    Two stages:
    1. Soft trim (60% threshold): Keep head + tail of old tool results
    2. Hard clear (80% threshold): Replace old tool results with placeholder

    Args:
        messages: The conversation messages array.
        context_window_tokens: Context window size in tokens.
        logger: Logger instance.

    Returns:
        Pruned messages array (may be a modified copy).
    """
    log = logger or _default_logger
    max_chars = context_window_tokens * CHARS_PER_TOKEN
    total_chars = estimate_total_chars(messages)

    if total_chars < max_chars * SOFT_TRIM_RATIO:
        return messages  # Under threshold, no pruning needed

    tool_result_indices = _find_tool_result_indices(messages)
    if len(tool_result_indices) <= KEEP_LAST_N_RESULTS:
        return messages  # Not enough tool results to prune

    prunable = tool_result_indices[:-KEEP_LAST_N_RESULTS]

    # Work on a copy to avoid mutating the original
    messages = copy.copy(messages)

    # Stage 1: Soft trim
    for idx in prunable:
        if total_chars < max_chars * SOFT_TRIM_RATIO:
            break

        msg = messages[idx]
        content = msg.get("content", "")
        min_size = SOFT_TRIM_HEAD_CHARS + SOFT_TRIM_TAIL_CHARS
        if not isinstance(content, str) or len(content) <= min_size:
            continue

        trimmed = _soft_trim_content(content, SOFT_TRIM_HEAD_CHARS, SOFT_TRIM_TAIL_CHARS)
        saved = len(content) - len(trimmed)
        total_chars -= saved
        messages[idx] = {**msg, "content": trimmed}
        tool_id = msg.get("tool_call_id", "?")
        log.debug(
            f"[context_manager] Soft-trimmed msg[{idx}] "
            f"(tool_call_id={tool_id}): "
            f"{len(content):,} → {len(trimmed):,} chars "
            f"(saved {saved:,})"
        )

    log.debug(
        f"[context_manager] After soft trim: {total_chars} chars "
        f"({total_chars / max_chars:.1%} of {max_chars})"
    )

    # Stage 2: Hard clear
    if total_chars > max_chars * HARD_CLEAR_RATIO:
        for idx in prunable:
            if total_chars < max_chars * HARD_CLEAR_RATIO:
                break

            msg = messages[idx]
            content = msg.get("content", "")
            if content == HARD_CLEAR_PLACEHOLDER:
                continue

            saved = len(content) - len(HARD_CLEAR_PLACEHOLDER)
            total_chars -= saved
            messages[idx] = {**msg, "content": HARD_CLEAR_PLACEHOLDER}
            tool_id = msg.get("tool_call_id", "?")
            log.debug(
                f"[context_manager] Hard-cleared msg[{idx}] "
                f"(tool_call_id={tool_id}): "
                f"{len(content):,} → {len(HARD_CLEAR_PLACEHOLDER)} chars "
                f"(saved {saved:,})"
            )

        log.debug(
            f"[context_manager] After hard clear: {total_chars} chars "
            f"({total_chars / max_chars:.1%} of {max_chars})"
        )

    return messages
