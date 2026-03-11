"""Enron Email entity schemas for evaluation.

Modeled after GmailMessageEntity — extends EmailEntity so the body is saved
as a file (plain text) and processed through the standard conversion pipeline.
Entity fields carry searchable metadata (subject, sender, recipients, etc.).
"""

from datetime import datetime
from typing import List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import EmailEntity


class EnronEmailEntity(EmailEntity):
    """Individual email from the Enron Email Dataset (CMU corpus)."""

    message_id: str = AirweaveField(
        ...,
        description=(
            "RFC 822 Message-ID header (e.g. '<17407857.1075840601283.JavaMail.evans@thyme>')"
        ),
        is_entity_id=True,
    )
    subject: str = AirweaveField(
        ...,
        description="Email subject line",
        is_name=True,
        embeddable=True,
    )
    sent_at: Optional[datetime] = AirweaveField(
        None,
        description="Email send date from the Date header",
        is_created_at=True,
    )
    sender: Optional[str] = AirweaveField(
        None,
        description="Sender email address (From header)",
        embeddable=True,
    )
    sender_name: Optional[str] = AirweaveField(
        None,
        description="Sender display name (X-From header, e.g. 'Davis, Pete')",
        embeddable=True,
    )
    to: List[str] = AirweaveField(
        default_factory=list,
        description="To recipients",
        embeddable=True,
    )
    cc: List[str] = AirweaveField(
        default_factory=list,
        description="CC recipients",
        embeddable=True,
    )
    snippet: Optional[str] = AirweaveField(
        None,
        description="Brief preview of the email body (first ~200 chars)",
        embeddable=True,
    )
    folder: Optional[str] = AirweaveField(
        None,
        description="Mailbox folder path (e.g. 'pete-davis/inbox')",
        embeddable=True,
    )
