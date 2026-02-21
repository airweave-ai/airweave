"""Message construction helpers for the agentic search conversation loop.

Builds the conversation messages array used by the tool-calling LLM interface.
All messages use a provider-generic OpenAI-compatible format. Each provider's
_call_api_with_tools() handles translation to its native format internally.

Message format:
- user:      {"role": "user", "content": "..."}
- assistant: {"role": "assistant", "content": "...", "tool_calls": [...]}
- tool:      {"role": "tool", "tool_call_id": "...", "content": "..."}
"""

import functools
from pathlib import Path

from airweave.search.agentic_search.external.llm.tool_response import LLMToolCall
from airweave.search.agentic_search.schemas.collection_metadata import (
    AgenticSearchCollectionMetadata,
)
from airweave.search.agentic_search.schemas.filter import (
    AgenticSearchFilterGroup,
    format_filter_groups_md,
)
from airweave.search.agentic_search.schemas.request import AgenticSearchMode

# Path to context markdown files
CONTEXT_DIR = Path(__file__).parent.parent / "context"


@functools.cache
def _load_static_prompt_parts() -> tuple[str, str]:
    """Load and cache the static prompt files (read once, reused forever)."""
    airweave_overview = (CONTEXT_DIR / "airweave_overview.md").read_text()
    agent_task = (CONTEXT_DIR / "agent_task.md").read_text()
    return airweave_overview, agent_task


def load_system_prompt(collection_metadata: AgenticSearchCollectionMetadata) -> str:
    """Build the full system prompt with static instructions and collection metadata.

    Static parts (airweave overview + agent task) are cached at module level.
    Only the collection metadata is dynamic per request.

    Args:
        collection_metadata: Metadata about the collection being searched.

    Returns:
        The complete system prompt string.
    """
    airweave_overview, agent_task = _load_static_prompt_parts()

    return f"""# Airweave Overview

{airweave_overview}

---

{agent_task}

---

## Collection Metadata

{collection_metadata.to_md()}"""


def build_initial_user_message(
    user_query: str,
    user_filter: list[AgenticSearchFilterGroup],
    mode: AgenticSearchMode,
) -> dict:
    """Build the first user message that starts the conversation."""
    filter_md = format_filter_groups_md(user_filter)
    mode_label = "direct" if mode == AgenticSearchMode.FAST else "agentic"

    content = f"""## Search Request

**Query:** {user_query}
**User filter:** {filter_md}
**Mode:** {mode_label}

Please search the collection to answer this query. Start with a broad semantic search."""

    return {"role": "user", "content": content}


def build_tool_result_message(tool_call_id: str, content: str) -> dict:
    """Build a tool result message (returned after tool execution)."""
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": content,
    }


def build_assistant_message(
    text: str | None,
    tool_calls: list[LLMToolCall] | None = None,
) -> dict:
    """Build an assistant message from the LLM response.

    Converts LLMToolCall dataclasses to the generic dict format expected
    by provider message converters (e.g., Anthropic's _build_assistant_blocks).
    """
    msg: dict = {"role": "assistant", "content": text or ""}
    if tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "function": {"name": tc.name, "arguments": tc.arguments},
            }
            for tc in tool_calls
        ]
    return msg
