"""Coda-specific Pydantic schemas for Monke test data generation."""

from pydantic import BaseModel, Field


class CodaDocSpec(BaseModel):
    """Spec for a Coda test doc."""

    title: str = Field(description="Doc title (should include token)")
    token: str = Field(description="Unique verification token for Monke")
    intro: str = Field(
        default="",
        description="Short intro text for the initial page (include token)",
    )
