"""Zendesk-specific Pydantic schemas used for LLM structured generation."""

from typing import List
from pydantic import BaseModel, Field
from typing_extensions import Literal


class ZendeskTicketSpec(BaseModel):
    subject: str = Field(description="The ticket subject - should be clear and descriptive")
    token: str = Field(description="Unique verification token to embed in the content")
    priority: Literal["low", "normal", "high", "urgent"] = Field(default="normal")
    status: Literal["new", "open", "pending", "hold", "solved", "closed"] = Field(default="open")
    ticket_type: Literal["question", "incident", "problem", "task"] = Field(default="question")
    tags: List[str] = Field(default_factory=list, description="Ticket tags/labels")


class ZendeskTicketContent(BaseModel):
    description: str = Field(description="Main ticket description with customer issue details")
    customer_info: str = Field(description="Customer context and environment details")
    steps_to_reproduce: List[str] = Field(description="Steps to reproduce the issue")
    expected_behavior: str = Field(description="What the customer expected to happen")
    actual_behavior: str = Field(description="What actually happened")
    additional_info: str = Field(description="Any additional relevant information")


class ZendeskTicket(BaseModel):
    """Schema for generating Zendesk ticket content."""

    spec: ZendeskTicketSpec
    content: ZendeskTicketContent
