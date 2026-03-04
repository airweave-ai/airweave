"""Intercom-specific Pydantic schemas used for LLM structured generation."""

from typing import List

from pydantic import BaseModel, Field


class IntercomTicketSpec(BaseModel):
    """Spec for an Intercom ticket."""

    default_title: str = Field(
        description="Ticket title - clear and descriptive, must include the verification token"
    )
    token: str = Field(description="Unique verification token to embed in the content")
    default_description: str = Field(
        description="Ticket description with customer issue details; must include the token"
    )


class IntercomTicketContent(BaseModel):
    """Content for an Intercom ticket."""

    description: str = Field(
        description="Main ticket description with customer issue details"
    )
    customer_info: str = Field(
        description="Customer context and environment details"
    )
    steps_to_reproduce: List[str] = Field(
        description="Steps to reproduce the issue"
    )
    expected_behavior: str = Field(
        description="What the customer expected to happen"
    )
    actual_behavior: str = Field(
        description="What actually happened"
    )


class IntercomTicket(BaseModel):
    """Schema for generating Intercom ticket content."""

    spec: IntercomTicketSpec
    content: IntercomTicketContent
