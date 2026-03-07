"""Debug / observability tooling for the agentic search loop.

Functions that run every iteration:
- dump_conversation: writes the full LLM payload to a JSON file
- log_token_breakdown: logs per-section token counts
- log_agent_response: logs thinking + search plans after LLM call
"""

import json
import logging
from pathlib import Path
from typing import Any

from airweave.search.agentic_search.external.llm.tool_response import LLMToolResponse
from airweave.search.agentic_search.external.tokenizer.interface import (
    AgenticSearchTokenizerInterface,
)

DEBUG_DUMP_PATH = str(Path(__file__).parent.parent / "conversation_dump.json")


def dump_conversation(
    iteration: int,
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    logger: logging.LoggerAdapter,
) -> None:
    """Write the full LLM payload as formatted JSON to DEBUG_DUMP_PATH.

    Overwrites the file each call. Strips internal _tool_name keys from messages.
    """
    try:
        cleaned_messages = []
        for msg in messages:
            cleaned = {k: v for k, v in msg.items() if k != "_tool_name"}
            cleaned_messages.append(cleaned)

        payload = {
            "iteration": iteration,
            "system_prompt": system_prompt,
            "messages": cleaned_messages,
            "tools": tools,
        }
        with open(DEBUG_DUMP_PATH, "w") as f:
            json.dump(payload, f, indent=2, default=str)
    except Exception:
        logger.warning("Failed to write conversation dump", exc_info=True)


def log_token_breakdown(
    iteration: int,
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tokenizer: AgenticSearchTokenizerInterface,
    logger: logging.LoggerAdapter,
) -> None:
    """Log a per-section token breakdown before the LLM call."""
    try:
        system_tokens = tokenizer.count_tokens(system_prompt)
        tools_tokens = tokenizer.count_tokens(json.dumps(tools, default=str))

        lines: list[str] = []
        total = system_tokens + tools_tokens

        lines.append(f"  system:{system_tokens:>30,}")
        lines.append(f"  tools:{tools_tokens:>31,}")

        # Walk messages and group them
        current_iter = -1  # -1 means we haven't seen an assistant msg yet
        for msg in messages:
            role = msg.get("role", "")
            if role == "user":
                tokens = tokenizer.count_tokens(msg.get("content", ""))
                total += tokens
                lines.append(f"  user:{tokens:>32,}")
            elif role == "assistant":
                current_iter += 1
                lines.append(f"  iteration {current_iter}:")
                content = msg.get("content", "")
                tokens = tokenizer.count_tokens(content)
                if msg.get("tool_calls"):
                    tokens += tokenizer.count_tokens(json.dumps(msg["tool_calls"], default=str))
                total += tokens
                lines.append(f"    assistant:{tokens:>26,}")
            elif role == "tool":
                tool_name = msg.get("_tool_name", "tool")
                tokens = tokenizer.count_tokens(msg.get("content", ""))
                total += tokens
                summarized_tag = ""
                content = msg.get("content", "")
                if (
                    tool_name == "search"
                    and content.startswith("**")
                    and "(metadata only" in content[:60]
                ):
                    summarized_tag = "  (summarized)"
                pad = max(20 - len(tool_name), 6)
                lines.append(f"    tool [{tool_name}]:{tokens:>{pad},}{summarized_tag}")

        sep = "  " + "\u2500" * 37
        lines.append(sep)
        lines.append(f"  total:{total:>31,}")

        header = f"[AgenticSearch] Token breakdown before iteration {iteration}:"
        logger.info("\n".join([header] + lines))
    except Exception:
        logger.warning("Failed to log token breakdown", exc_info=True)


def log_agent_response(
    iteration: int,
    response: LLMToolResponse,
    logger: logging.LoggerAdapter,
) -> None:
    """Log the agent's thinking and tool calls (search plans) after the LLM call."""
    try:
        lines: list[str] = []

        if response.thinking:
            lines.append(f"  thinking:\n{_indent(response.thinking, 4)}")
        if response.text:
            lines.append(f"  text:\n{_indent(response.text, 4)}")

        if response.tool_calls:
            for tc in response.tool_calls:
                args = tc.arguments
                if isinstance(args, dict):
                    args_str = json.dumps(args, indent=2, default=str)
                else:
                    args_str = str(args)
                lines.append(f"  tool_call: {tc.name}\n{_indent(args_str, 4)}")
        else:
            lines.append("  (no tool calls — agent is done)")

        header = f"[AgenticSearch] Iteration {iteration} response:"
        logger.info("\n".join([header] + lines))
    except Exception:
        logger.warning("Failed to log agent response", exc_info=True)


def _indent(text: str, spaces: int) -> str:
    """Indent each line of text."""
    prefix = " " * spaces
    return "\n".join(prefix + line for line in text.splitlines())
