"""Answer schema for spotlight search."""

from pydantic import BaseModel, Field


class SpotlightCitation(BaseModel):
    """Citation schema for spotlight search."""

    entity_id: str = Field(..., description="The entity ID")


class SpotlightAnswer(BaseModel):
    """Answer schema for spotlight search."""

    text: str = Field(..., description="The answer text")
    citations: list[SpotlightCitation] = Field(..., description="The citations")
