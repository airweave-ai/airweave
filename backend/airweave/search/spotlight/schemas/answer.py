"""Answer schema for spotlight search."""

from pydantic import BaseModel, Field


class SpotlightCitation(BaseModel):
    """Citation for a source used in the answer."""

    entity_id: str = Field(..., description="The entity ID of a search result used in the answer")


class SpotlightAnswer(BaseModel):
    """Answer generated from search results."""

    text: str = Field(
        ...,
        description="The answer text. Should be clear and well-structured.",
    )
    citations: list[SpotlightCitation] = Field(
        ...,
        description="List of entity_ids from search results used to compose the answer.",
    )
