"""Enron Email entity schemas for evaluation."""

from datetime import datetime
from typing import Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class EnronEmailEntity(BaseEntity):
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
    body: str = AirweaveField(
        ...,
        description="Email body text",
        embeddable=True,
    )
    sender: str = AirweaveField(
        ...,
        description="Sender email address",
        embeddable=True,
    )
    recipients: str = AirweaveField(
        ...,
        description="Comma-separated recipient email addresses (To + Cc)",
        embeddable=True,
    )
    date: Optional[datetime] = AirweaveField(
        None,
        description="Email send date",
        is_created_at=True,
    )
    folder: Optional[str] = AirweaveField(
        None,
        description="Mailbox folder path (e.g. 'pete-davis/Inbox')",
    )
