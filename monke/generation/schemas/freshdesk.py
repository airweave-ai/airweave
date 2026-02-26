"""Freshdesk-specific Pydantic schemas used for LLM structured generation."""

from typing import List
from pydantic import BaseModel, Field
from typing_extensions import Literal


class FreshdeskTicketSpec(BaseModel):
    subject: str = Field(description="The ticket subject - clear and descriptive")
    token: str = Field(description="Unique verification token to embed in the content")
    priority: Literal["low", "medium", "high", "urgent"] = Field(default="medium")
    status: Literal["open", "pending", "resolved", "closed"] = Field(default="open")
    ticket_type: Literal["question", "problem", "task"] = Field(default="question")


class FreshdeskTicketContent(BaseModel):
    description: str = Field(description="Main ticket description with customer issue details")
    customer_info: str = Field(description="Customer context and environment details")
    steps_to_reproduce: List[str] = Field(description="Steps to reproduce the issue")
    expected_behavior: str = Field(description="What the customer expected to happen")
    actual_behavior: str = Field(description="What actually happened")
    additional_info: str = Field(description="Any additional relevant information")


class FreshdeskTicket(BaseModel):
    """Schema for generating Freshdesk ticket content."""

    spec: FreshdeskTicketSpec
    content: FreshdeskTicketContent
