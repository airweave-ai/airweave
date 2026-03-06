"""Entity schemas for Intercom.

Reference:
    https://developers.intercom.com/docs/references/rest-api/conversations
    https://developers.intercom.com/docs/references/rest-api/api.intercom.io/tickets
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class IntercomConversationEntity(BaseEntity):
    """Schema for Intercom conversation entities.

    A conversation is a thread of messages between contacts and teammates.
    """

    conversation_id: str = AirweaveField(
        ...,
        description="Unique identifier of the conversation",
        embeddable=False,
        is_entity_id=True,
    )
    subject: str = AirweaveField(
        ...,
        description="Subject or first message preview of the conversation",
        embeddable=True,
        is_name=True,
    )
    created_at_value: Optional[datetime] = AirweaveField(
        None,
        description="When the conversation was created",
        embeddable=True,
        is_created_at=True,
    )
    updated_at_value: Optional[datetime] = AirweaveField(
        None,
        description="When the conversation was last updated",
        embeddable=True,
        is_updated_at=True,
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the conversation in Intercom",
        embeddable=False,
        unhashable=True,
    )

    state: Optional[str] = AirweaveField(
        None,
        description="Conversation state (open, closed, snoozed)",
        embeddable=True,
    )
    priority: Optional[str] = AirweaveField(
        None,
        description="Priority level",
        embeddable=True,
    )
    assignee_name: Optional[str] = AirweaveField(
        None,
        description="Name of the teammate assigned",
        embeddable=True,
    )
    assignee_email: Optional[str] = AirweaveField(
        None,
        description="Email of the teammate assigned",
        embeddable=True,
    )
    contact_ids: List[str] = AirweaveField(
        default_factory=list,
        description="IDs of contacts in the conversation",
        embeddable=False,
    )
    custom_attributes: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Custom attributes on the conversation",
        embeddable=True,
    )
    tags: List[str] = AirweaveField(
        default_factory=list,
        description="Tag names applied to the conversation",
        embeddable=True,
    )
    source_body: Optional[str] = AirweaveField(
        None,
        description="Body of the first message (source)",
        embeddable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the Intercom conversation URL."""
        return self.web_url_value or ""


class IntercomConversationMessageEntity(BaseEntity):
    """Schema for a single message (conversation part) within an Intercom conversation."""

    message_id: str = AirweaveField(
        ...,
        description="Unique identifier of the conversation part",
        embeddable=False,
        is_entity_id=True,
    )
    conversation_id: str = AirweaveField(
        ...,
        description="ID of the parent conversation",
        embeddable=False,
    )
    conversation_subject: str = AirweaveField(
        ...,
        description="Subject of the parent conversation",
        embeddable=True,
        is_name=True,
    )
    body: str = AirweaveField(
        ...,
        description="Message body (plain text or HTML)",
        embeddable=True,
    )
    created_at_value: Optional[datetime] = AirweaveField(
        None,
        description="When the message was created",
        embeddable=True,
        is_created_at=True,
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the conversation (and message) in Intercom",
        embeddable=False,
        unhashable=True,
    )

    part_type: Optional[str] = AirweaveField(
        None,
        description="Type of part (comment, assignment, etc.)",
        embeddable=True,
    )
    author_id: Optional[str] = AirweaveField(
        None,
        description="ID of the author",
        embeddable=False,
    )
    author_type: Optional[str] = AirweaveField(
        None,
        description="Author type (admin, user, lead, bot)",
        embeddable=True,
    )
    author_name: Optional[str] = AirweaveField(
        None,
        description="Display name of the author",
        embeddable=True,
    )
    author_email: Optional[str] = AirweaveField(
        None,
        description="Email of the author",
        embeddable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the Intercom message/conversation URL."""
        return self.web_url_value or ""


class IntercomTicketEntity(BaseEntity):
    """Schema for Intercom ticket entities.

    Tickets are used for structured support workflows.
    """

    ticket_id: str = AirweaveField(
        ...,
        description="Unique identifier of the ticket",
        embeddable=False,
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Ticket name/title",
        embeddable=True,
        is_name=True,
    )
    description: Optional[str] = AirweaveField(
        None,
        description="Ticket description",
        embeddable=True,
    )
    created_at_value: Optional[datetime] = AirweaveField(
        None,
        description="When the ticket was created",
        embeddable=True,
        is_created_at=True,
    )
    updated_at_value: Optional[datetime] = AirweaveField(
        None,
        description="When the ticket was last updated",
        embeddable=True,
        is_updated_at=True,
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the ticket in Intercom",
        embeddable=False,
        unhashable=True,
    )

    state: Optional[str] = AirweaveField(
        None,
        description="Ticket state (open, closed, etc.)",
        embeddable=True,
    )
    priority: Optional[str] = AirweaveField(
        None,
        description="Priority level",
        embeddable=True,
    )
    assignee_id: Optional[str] = AirweaveField(
        None,
        description="ID of the assignee",
        embeddable=False,
    )
    assignee_name: Optional[str] = AirweaveField(
        None,
        description="Name of the assignee",
        embeddable=True,
    )
    contact_id: Optional[str] = AirweaveField(
        None,
        description="ID of the contact",
        embeddable=False,
    )
    ticket_type_id: Optional[str] = AirweaveField(
        None,
        description="Ticket type ID",
        embeddable=False,
    )
    ticket_type_name: Optional[str] = AirweaveField(
        None,
        description="Ticket type name",
        embeddable=True,
    )
    ticket_parts_text: Optional[str] = AirweaveField(
        None,
        description="Concatenated body text of ticket parts (replies, comments, notes) for search",
        embeddable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the Intercom ticket URL."""
        return self.web_url_value or ""
