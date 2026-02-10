"""Answer schema for agentic search."""

from pydantic import BaseModel, Field


class AgenticSearchCitation(BaseModel):
    """Citation for a source used in the answer."""

    entity_id: str = Field(..., description="The entity ID of a search result used in the answer")


class AgenticSearchAnswer(BaseModel):
    """Answer generated from search results."""

    text: str = Field(
        ...,
        description="The answer text. Should be clear and well-structured.",
    )
    citations: list[AgenticSearchCitation] = Field(
        ...,
        description="List of entity_ids from search results used to compose the answer.",
    )
