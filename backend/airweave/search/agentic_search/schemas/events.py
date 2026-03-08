"""Event schemas for agentic search streaming.

Typed events emitted during agentic search to give users transparency
into the agent's reasoning process. Each event has a `type` literal
discriminator for clean JSON serialization and frontend consumption.

Events:
- thinking: Model's reasoning text + LLM usage stats (once per iteration)
- tool_call: A tool was executed (with arguments, result summary, timing)
- done: Search complete with final response
- error: An error occurred during search
"""

from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, Field

from airweave.search.agentic_search.schemas.response import AgenticSearchResponse


class AgenticSearchThinkingEvent(BaseModel):
    """Emitted once per iteration after the LLM responds.

    Contains the model's reasoning text and LLM usage statistics.
    This is the single source of truth for per-iteration metadata.
    """

    type: Literal["thinking"] = "thinking"
    iteration: int = Field(..., description="Current iteration number (0-indexed).")
    text: str = Field(..., description="The model's reasoning text.")
    # LLM usage (populated from the LLM response)
    prompt_tokens: int = Field(0, description="Prompt tokens used by this LLM call.")
    completion_tokens: int = Field(0, description="Completion tokens used by this LLM call.")
    cache_creation_input_tokens: int = Field(0, description="Tokens written to prompt cache.")
    cache_read_input_tokens: int = Field(0, description="Tokens read from prompt cache.")
    tool_calls_count: int = Field(0, description="Number of tool calls in this iteration.")
    stop_reason: str = Field("", description="Why the model stopped (tool_use, end_turn, etc).")
    # Cumulative state
    total_results_seen: int = Field(0, description="Cumulative unique results across all iterations.")
    total_results_marked: int = Field(0, description="Total results marked as relevant so far.")


class AgenticSearchToolCallEvent(BaseModel):
    """Emitted after each tool call completes.

    Generic for all tools — the tool_name + arguments + result_summary
    give full visibility into what happened.
    """

    type: Literal["tool_call"] = "tool_call"
    iteration: int = Field(..., description="Current iteration number (0-indexed).")
    tool_call_id: str = Field(..., description="The tool call ID from the LLM.")
    tool_name: str = Field(
        ...,
        description="Tool name: search, mark_as_relevant, read_previous_results, finish.",
    )
    arguments: dict = Field(default_factory=dict, description="Raw LLM arguments for the tool call.")
    result_summary: dict = Field(
        default_factory=dict,
        description="Structured summary of the tool result (compact, no full content).",
    )
    duration_ms: int = Field(..., description="Time taken for the tool call (ms).")


class AgenticSearchDoneEvent(BaseModel):
    """Emitted when the search is complete.

    Contains the full response with results.
    """

    type: Literal["done"] = "done"
    response: AgenticSearchResponse = Field(..., description="The complete search response.")


class AgenticSearchErrorEvent(BaseModel):
    """Emitted when an error occurs during search."""

    type: Literal["error"] = "error"
    message: str = Field(..., description="Error description.")


AgenticSearchEvent = Annotated[
    Union[
        AgenticSearchThinkingEvent,
        AgenticSearchToolCallEvent,
        AgenticSearchDoneEvent,
        AgenticSearchErrorEvent,
    ],
    Field(discriminator="type"),
]
