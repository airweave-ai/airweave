"""Event schemas for spotlight search streaming.

Typed events emitted during spotlight search to give users transparency
into the agent's reasoning process. Each event has a `type` literal
discriminator for clean JSON serialization and frontend consumption.
"""

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

from airweave.search.spotlight.schemas.response import SpotlightResponse


class SpotlightPlanningEvent(BaseModel):
    """Emitted after the planner generates a search plan.

    Shows the agent's reasoning about what to search for and why.
    """

    type: Literal["planning"] = "planning"
    iteration: int = Field(..., description="Current iteration number (0-indexed).")
    reasoning: str = Field(..., description="The planner's reasoning for this search plan.")
    query: str = Field(..., description="The primary search query chosen.")
    strategy: str = Field(..., description="Retrieval strategy (semantic, keyword, hybrid).")


class SpotlightSearchingEvent(BaseModel):
    """Emitted after search execution completes.

    Shows how many results were found and how long the search took.
    """

    type: Literal["searching"] = "searching"
    iteration: int = Field(..., description="Current iteration number (0-indexed).")
    result_count: int = Field(..., description="Number of search results returned.")
    duration_ms: int = Field(
        ..., description="Time taken for query compilation and execution (ms)."
    )


class SpotlightEvaluatingEvent(BaseModel):
    """Emitted after the evaluator assesses search results.

    Shows the agent's assessment and, if continuing, what it will try next.
    """

    type: Literal["evaluating"] = "evaluating"
    iteration: int = Field(..., description="Current iteration number (0-indexed).")
    reasoning: str = Field(..., description="The evaluator's assessment of the results.")
    should_continue: bool = Field(..., description="Whether the agent will search again.")
    advice: Optional[str] = Field(
        default=None, description="Guidance for the next iteration (if continuing)."
    )


class SpotlightDoneEvent(BaseModel):
    """Emitted when the search is complete.

    Contains the full response with results and composed answer.
    """

    type: Literal["done"] = "done"
    response: SpotlightResponse = Field(..., description="The complete search response.")


class SpotlightErrorEvent(BaseModel):
    """Emitted when an error occurs during search."""

    type: Literal["error"] = "error"
    message: str = Field(..., description="Error description.")


SpotlightEvent = Annotated[
    Union[
        SpotlightPlanningEvent,
        SpotlightSearchingEvent,
        SpotlightEvaluatingEvent,
        SpotlightDoneEvent,
        SpotlightErrorEvent,
    ],
    Field(discriminator="type"),
]
