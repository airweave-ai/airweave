"""Message formatting for the agentic search agent.

Pure formatting — converts data into the dict shape the LLM expects.
No context window logic (that's the context manager).

Functions:
- build_system_prompt: static prompts + collection metadata → system prompt string
- build_user_message: query + filters → first user message dict
- build_assistant_message: LLMResponse → assistant message dict
- build_tool_result_message: tool output string → tool result message dict
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

from airweave.core.protocols.llm import LLMResponse
from airweave.domains.search.types.filters import FilterGroup, format_filter_groups_md
from airweave.domains.search.types.metadata import CollectionMetadata


@functools.cache
def _load_prompt_parts() -> tuple[str, str]:
    """Load and cache the static prompt files (read once, reused forever)."""
    context_dir = Path(__file__).parent / "context"
    overview = (context_dir / "airweave_overview.md").read_text()
    task = (context_dir / "agent_task.md").read_text()
    return overview, task


def build_system_prompt(
    metadata: CollectionMetadata,
    max_iterations: int,
) -> str:
    """Assemble the full system prompt from static prompts + collection metadata."""
    overview, task = _load_prompt_parts()
    task = task.replace("{max_iterations}", str(max_iterations))
    return (
        f"# Airweave Overview\n\n{overview}\n\n"
        f"---\n\n{task}\n\n"
        f"---\n\n## Collection Metadata\n\n{metadata.to_md()}"
    )


def build_user_message(query: str, filters: list[FilterGroup]) -> dict[str, str]:
    """Format the initial user message with query and filters."""
    filter_md = format_filter_groups_md(filters) if filters else "None"
    content = f"## Search Request\n**Query:** {query}\n**User filter:** {filter_md}"
    return {"role": "user", "content": content}


def build_assistant_message(response: LLMResponse) -> dict[str, Any]:
    """Convert an LLM response to an assistant message dict.

    The ``_thinking`` field is an internal marker that each LLM adapter
    converts to the provider-appropriate format via ``_prepare_messages_for_api``:

    - **Anthropic**: native ``thinking`` content blocks.
    - **Together AI**: ``reasoning`` field on assistant messages
      (preserved thinking for KV cache reuse).
    - **Cerebras**: embedded in ``content``
      (GPT-OSS: raw prepend; GLM/Qwen: ``<think>`` tags).
    - **Groq**: stripped entirely (Groq docs warn it degrades output).
    """
    msg: dict[str, Any] = {
        "role": "assistant",
        "content": response.text,
        "_thinking": response.thinking,
    }

    if response.tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": tc.arguments,
                },
            }
            for tc in response.tool_calls
        ]

    return msg


def build_tool_result_message(
    tool_call_id: str,
    tool_name: str,
    content: str,
) -> dict[str, str]:
    """Wrap tool output as a tool result message.

    The `_tool_name` field is an internal marker used by the context manager
    to know which tool produced this result (search results get compressed
    differently than read results). It's not sent to the LLM — the adapter
    strips unknown fields during message conversion.
    """
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": content,
        "_tool_name": tool_name,
    }
