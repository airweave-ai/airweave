"""Request schemas for spotlight search."""

from pydantic import BaseModel, Field, field_validator


class SpotlightRequest(BaseModel):
    """Request schema for spotlight search."""

    query: str = Field(..., description="The natural language search query")

    @field_validator("query")
    @classmethod
    def validate_query_not_empty(cls, v: str) -> str:
        """Validate that query is not empty."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        return v
