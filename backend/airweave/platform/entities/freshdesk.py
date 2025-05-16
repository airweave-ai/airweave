"""
Freshdesk entity definitions for Airweave.

This module defines schemas for Freshdesk entities including:
- Groups
- Tickets
- Conversations

References:
    https://developers.freshdesk.com/api/#groups
    https://developers.freshdesk.com/api/#tickets
    https://developers.freshdesk.com/api/#conversations
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._base import Breadcrumb, ChunkEntity


class FreshdeskGroupEntity(ChunkEntity):
    """Freshdesk group entity."""

    entity_id: str = Field(..., description="Unique Entity ID")
    group_id: str = Field(..., description="Group ID")
    name: str = Field(..., description="Group name")
    description: Optional[str] = Field(None, description="Group description")
    escalate_to: Optional[int] = Field(None, description="ID of the user to whom tickets are escalated")
    unassigned_for: Optional[str] = Field(None, description="SLA for unassigned tickets in the group")
    business_hours_id: Optional[int] = Field(None, description="ID of the business hours configuration")
    agent_ids: List[int] = Field(default_factory=list, description="List of agent IDs in the group")
    created_at: Optional[datetime] = Field(None, description="Timestamp when the group was created")
    updated_at: Optional[datetime] = Field(None, description="Timestamp when the group was last updated")


class FreshdeskTicketEntity(ChunkEntity):
    """Freshdesk ticket entity."""

    entity_id: str = Field(..., description="Unique Entity ID")
    breadcrumbs: List[Breadcrumb] = Field(
        default_factory=list, description="Breadcrumb hierarchy (e.g., parent group)"
    )
    ticket_id: str = Field(..., description="Ticket ID")
    subject: str = Field(..., description="Subject of the ticket")
    description: Optional[str] = Field("", description="Description of the ticket")
    description_text: Optional[str] = Field("", description="Plain text version of the description")
    status: Optional[int] = Field(None, description="Status ID of the ticket")
    priority: Optional[int] = Field(None, description="Priority ID of the ticket")
    source: Optional[int] = Field(None, description="Source ID of the ticket (e.g., email, chat)")
    requester_id: Optional[int] = Field(None, description="ID of the ticket requester")
    responder_id: Optional[int] = Field(None, description="ID of the agent assigned to the ticket")
    group_id: Optional[str] = Field(None, description="ID of the group the ticket is assigned to")
    tags: List[str] = Field(default_factory=list, description="Tags associated with the ticket")
    custom_fields: Dict[str, Any] = Field(
        default_factory=dict, description="Custom fields for the ticket"
    )
    created_at: Optional[datetime] = Field(None, description="Timestamp when the ticket was created")
    updated_at: Optional[datetime] = Field(None, description="Timestamp when the ticket was last updated")
    due_by: Optional[datetime] = Field(None, description="Timestamp when the ticket is due")
    fr_due_by: Optional[datetime] = Field(None, description="Timestamp for first response due date")


class FreshdeskConversationEntity(ChunkEntity):
    """Freshdesk conversation entity."""

    entity_id: str = Field(..., description="Unique Entity ID")
    breadcrumbs: List[Breadcrumb] = Field(
        default_factory=list, description="Breadcrumb hierarchy (e.g., parent group and ticket)"
    )
    conversation_id: str = Field(..., description="Conversation ID")
    ticket_id: str = Field(..., description="Parent ticket ID")
    body: Optional[str] = Field("", description="HTML content of the conversation")
    body_text: Optional[str] = Field("", description="Plain text version of the conversation")
    user_id: Optional[int] = Field(None, description="ID of the user who created the conversation")
    to_emails: List[str] = Field(default_factory=list, description="List of recipient email addresses")
    cc_emails: List[str] = Field(default_factory=list, description="List of CC email addresses")
    bcc_emails: List[str] = Field(default_factory=list, description="List of BCC email addresses")
    incoming: bool = Field(False, description="Whether the conversation is incoming")
    private: bool = Field(False, description="Whether the conversation is private (internal note)")
    created_at: Optional[datetime] = Field(None, description="Timestamp when the conversation was created")
    updated_at: Optional[datetime] = Field(None, description="Timestamp when the conversation was last updated")