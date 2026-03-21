"""Entity schemas for Intercom.

Reference:
    https://developers.intercom.com/docs/references/rest-api/conversations
    https://developers.intercom.com/docs/references/rest-api/api.intercom.io/tickets
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb


def _parse_intercom_ts(value: Any) -> Optional[datetime]:
    """Parse Intercom Unix timestamp (seconds) to timezone-aware datetime."""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        if isinstance(value, str):
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        pass
    return None


def _strip_html(html: Optional[str]) -> str:
    """Strip HTML tags for plain-text subject/body; return empty string if None."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    return " ".join(text.split()).strip() or ""


def _unwrap_list(value: Any, inner_key: str) -> List[Dict[str, Any]]:
    """Extract list from Intercom API list objects.

    Conversations return teammates as { "type": "admin.list", "teammates": [...] }
    and contacts as an object containing the list.  If *value* is already a plain
    list of dicts, return it; if it is a dict, return the inner list; otherwise [].
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        inner = value.get(inner_key) or value.get("data")
        if isinstance(inner, list):
            return [x for x in inner if isinstance(x, dict)]
    return []


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

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        breadcrumbs: List[Breadcrumb],
        web_url: str,
    ) -> IntercomConversationEntity:
        """Build from an Intercom API conversation object."""
        conv_id = str(data.get("id", ""))
        now = datetime.now(timezone.utc)
        created_at = _parse_intercom_ts(data.get("created_at")) or now
        updated_at = _parse_intercom_ts(data.get("updated_at")) or created_at

        source_obj = data.get("source") or {}
        subject = _strip_html(source_obj.get("subject") or source_obj.get("body"))
        if not subject:
            subject = f"Conversation {conv_id}"

        teammates = _unwrap_list(data.get("teammates"), "teammates")
        assignee_name = None
        assignee_email = None
        admin_assignee_id = data.get("admin_assignee_id")
        if admin_assignee_id is not None:
            for t in teammates:
                if str(t.get("id")) == str(admin_assignee_id):
                    assignee_name = t.get("name")
                    assignee_email = t.get("email")
                    break

        custom_attrs = data.get("custom_attributes") or {}
        tags_list = _unwrap_list(data.get("tags"), "tags")
        tag_names = [str(t.get("name", "")) for t in tags_list if t.get("name")]
        contacts_list = _unwrap_list(data.get("contacts"), "contacts")
        contact_ids = [str(c.get("id", "")) for c in contacts_list if c.get("id")]

        return cls(
            entity_id=conv_id,
            breadcrumbs=breadcrumbs,
            name=subject[:500],
            created_at=created_at,
            updated_at=updated_at,
            conversation_id=conv_id,
            subject=subject[:500],
            created_at_value=created_at,
            updated_at_value=updated_at,
            web_url_value=web_url,
            state=data.get("state"),
            priority=data.get("priority"),
            assignee_name=assignee_name,
            assignee_email=assignee_email,
            contact_ids=contact_ids,
            custom_attributes=custom_attrs,
            tags=tag_names,
            source_body=_strip_html(source_obj.get("body")),
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

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        breadcrumbs: List[Breadcrumb],
        conversation_id: str,
        conversation_subject: str,
        web_url: str,
    ) -> IntercomConversationMessageEntity:
        """Build from an Intercom conversation-part API object."""
        part_id = str(data.get("id", ""))
        body = data.get("body") or ""
        created_at = _parse_intercom_ts(data.get("created_at"))

        author_raw = data.get("author")
        author = author_raw if isinstance(author_raw, dict) else {}
        author_id = str(author.get("id", "")) if author.get("id") else None

        return cls(
            entity_id=part_id,
            breadcrumbs=breadcrumbs,
            name=body[:200] if body else f"Message {part_id}",
            created_at=created_at,
            updated_at=created_at,
            message_id=part_id,
            conversation_id=conversation_id,
            conversation_subject=conversation_subject[:500],
            body=body,
            created_at_value=created_at,
            web_url_value=web_url,
            part_type=data.get("part_type"),
            author_id=author_id,
            author_type=author.get("type"),
            author_name=author.get("name"),
            author_email=author.get("email"),
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

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        breadcrumbs: List[Breadcrumb],
        web_url: str,
        ticket_parts_text: Optional[str] = None,
    ) -> IntercomTicketEntity:
        """Build from an Intercom API ticket object.

        The *ticket_parts_text* kwarg should be pre-fetched by the source
        (requires async I/O) and passed in ready-made.
        """
        ticket_id = str(data.get("id", ""))
        attrs = data.get("ticket_attributes") or {}
        name = (
            data.get("name")
            or data.get("default_title")
            or attrs.get("default_title")
            or f"Ticket {ticket_id}"
        )
        desc = (
            data.get("description")
            or data.get("default_description")
            or attrs.get("default_description")
        )

        now = datetime.now(timezone.utc)
        created_at = _parse_intercom_ts(data.get("created_at")) or now
        updated_at = _parse_intercom_ts(data.get("updated_at")) or created_at

        assignee_raw = data.get("assignee")
        assignee = assignee_raw if isinstance(assignee_raw, dict) else {}
        assignee_id = str(assignee.get("id", "")) if assignee.get("id") else None
        assignee_name = assignee.get("name")

        ticket_type_raw = data.get("ticket_type")
        ticket_type = ticket_type_raw if isinstance(ticket_type_raw, dict) else {}
        type_name = ticket_type.get("name")
        type_id = str(ticket_type.get("id", "")) if ticket_type.get("id") else None

        contacts_list = _unwrap_list(data.get("contacts"), "contacts")
        if not contacts_list and data.get("contact_ids"):
            contact_ids_raw = data.get("contact_ids")
            if isinstance(contact_ids_raw, list):
                contact_id = str(contact_ids_raw[0]) if contact_ids_raw else None
            else:
                contact_id = str(contact_ids_raw) if contact_ids_raw else None
        else:
            contact_id = str(contacts_list[0].get("id", "")) if contacts_list else None

        return cls(
            entity_id=ticket_id,
            breadcrumbs=breadcrumbs,
            name=name,
            created_at=created_at,
            updated_at=updated_at,
            ticket_id=ticket_id,
            description=desc,
            created_at_value=created_at,
            updated_at_value=updated_at,
            web_url_value=web_url,
            state=data.get("state") or data.get("ticket_state"),
            priority=data.get("priority"),
            assignee_id=assignee_id,
            assignee_name=assignee_name,
            contact_id=contact_id,
            ticket_type_id=type_id,
            ticket_type_name=type_name,
            ticket_parts_text=ticket_parts_text,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the Intercom ticket URL."""
        return self.web_url_value or ""
