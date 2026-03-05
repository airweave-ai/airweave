"""Slab-specific Pydantic schemas for test content generation."""

from pydantic import BaseModel, Field


class SlabTopicContent(BaseModel):
    """Content for a Slab topic."""

    name: str = Field(description="Topic name; must include the verification token")
    description: str = Field(
        default="",
        description="Short topic description (optional); token can appear here",
    )


class SlabPostContent(BaseModel):
    """Content for a Slab post (title + body as plain text for delta conversion)."""

    title: str = Field(description="Post title; must include the verification token")
    body_plain: str = Field(
        default="",
        description="Post body as plain text; token can appear here",
    )
