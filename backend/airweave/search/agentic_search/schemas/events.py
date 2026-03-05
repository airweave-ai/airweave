"""Event schemas for agentic search streaming.

Typed events emitted during agentic search to give users transparency
into the agent's reasoning process. Each event has a `type` literal
discriminator for clean JSON serialization and frontend consumption.

Events:
- thinking: Model's reasoning text between tool calls
- searching: Search execution completed (result count + timing)
- mark_relevant: Agent saved entities as relevant for the final answer
- done: Search complete with final response
- error: An error occurred during search
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from airweave.search.agentic_search.schemas.response import AgenticSearchResponse


class AgenticSearchThinkingEvent(BaseModel):
    """Emitted when the model produces reasoning text.

    Contains the model's inner monologue — its reasoning about what
    it's found so far and what to try next. Replaces the old separate
    PlanningEvent and EvaluatingEvent.
    """

    type: Literal["thinking"] = "thinking"
    iteration: int = Field(..., description="Current iteration number (0-indexed).")
    text: str = Field(..., description="The model's reasoning text.")


class AgenticSearchingEvent(BaseModel):
    """Emitted after search execution completes.

    Shows how many results were found and how long the search took.
    """

    type: Literal["searching"] = "searching"
    iteration: int = Field(..., description="Current iteration number (0-indexed).")
    result_count: int = Field(..., description="Number of search results returned.")
    duration_ms: int = Field(
        ..., description="Time taken for query compilation and execution (ms)."
    )


class AgenticSearchMarkRelevantEvent(BaseModel):
    """Emitted when the agent saves entities as relevant.

    Tracks which entity IDs the agent curated and the running total,
    giving visibility into the result accumulation process.
    """

    type: Literal["mark_relevant"] = "mark_relevant"
    iteration: int = Field(..., description="Current iteration number (0-indexed).")
    marked_ids: list[str] = Field(..., description="Entity IDs saved in this call.")
    not_found_ids: list[str] = Field(
        default_factory=list,
        description="Entity IDs requested but not found in any prior search results.",
    )
    total_relevant: int = Field(
        ..., description="Total number of curated relevant results after this call."
    )


class AgenticSearchDoneEvent(BaseModel):
    """Emitted when the search is complete.

    Contains the full response with results and composed answer.
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
        AgenticSearchingEvent,
        AgenticSearchMarkRelevantEvent,
        AgenticSearchDoneEvent,
        AgenticSearchErrorEvent,
    ],
    Field(discriminator="type"),
]
