"""Entity schemas for Apollo.

MVP entities: Contacts, Accounts, Sequences, Email Activities.
API reference: https://docs.apollo.io/
"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import Field, computed_field, field_validator

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


def _parse_apollo_datetime(value: Any) -> Optional[datetime]:
    """Parse Apollo datetime (ISO string or None)."""
    if not value or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None
    return None


class ApolloAccountEntity(BaseEntity):
    """Schema for Apollo account (company) entities.

    From POST /accounts/search. Accounts are companies added to your Apollo database.
    """

    account_id: str = AirweaveField(..., description="Apollo account ID.", is_entity_id=True)
    name: str = AirweaveField(
        ..., description="Account/company name.", is_name=True, embeddable=True
    )
    domain: Optional[str] = AirweaveField(
        None, description="Primary domain of the account.", embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the account was created.", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="When the account was last updated.", is_updated_at=True
    )
    source: Optional[str] = AirweaveField(
        None, description="Source of the account (e.g. api, csv_import).", embeddable=True
    )
    source_display_name: Optional[str] = AirweaveField(
        None, description="Human-readable source name.", embeddable=True
    )
    num_contacts: Optional[int] = Field(
        None, description="Number of contacts linked to this account."
    )
    last_activity_date: Optional[datetime] = AirweaveField(
        None, description="Last activity date on the account.", embeddable=True
    )
    label_ids: List[str] = Field(
        default_factory=list, description="Label IDs applied to the account."
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this account in Apollo.",
        embeddable=False,
        unhashable=True,
    )

    @field_validator("created_at", "updated_at", "last_activity_date", mode="before")
    @classmethod
    def parse_datetime_fields(cls, value: Any) -> Optional[datetime]:
        """Parse Apollo datetime (ISO string or None) to datetime."""
        return _parse_apollo_datetime(value)

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the web URL to view this account in Apollo, or empty string."""
        return self.web_url_value or ""


class ApolloContactEntity(BaseEntity):
    """Schema for Apollo contact entities.

    From POST /contacts/search. Contacts are people added to your Apollo database.
    """

    contact_id: str = AirweaveField(..., description="Apollo contact ID.", is_entity_id=True)
    name: str = AirweaveField(
        ..., description="Full name of the contact.", is_name=True, embeddable=True
    )
    first_name: Optional[str] = AirweaveField(None, description="First name.", embeddable=True)
    last_name: Optional[str] = AirweaveField(None, description="Last name.", embeddable=True)
    email: Optional[str] = AirweaveField(None, description="Email address.", embeddable=True)
    title: Optional[str] = AirweaveField(None, description="Job title.", embeddable=True)
    organization_name: Optional[str] = AirweaveField(
        None, description="Current organization name.", embeddable=True
    )
    account_id: Optional[str] = Field(
        None, description="Apollo account ID this contact belongs to."
    )
    account_name: Optional[str] = AirweaveField(
        None, description="Account/company name.", embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the contact was created.", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="When the contact was last updated.", is_updated_at=True
    )
    email_status: Optional[str] = AirweaveField(
        None, description="Email verification status.", embeddable=True
    )
    source_display_name: Optional[str] = AirweaveField(
        None, description="Human-readable source.", embeddable=True
    )
    emailer_campaign_ids: List[str] = Field(
        default_factory=list, description="Sequence IDs the contact is in."
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this contact in Apollo.",
        embeddable=False,
        unhashable=True,
    )

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime_fields(cls, value: Any) -> Optional[datetime]:
        """Parse Apollo datetime (ISO string or None) to datetime."""
        return _parse_apollo_datetime(value)

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the web URL to view this contact in Apollo, or empty string."""
        return self.web_url_value or ""


class ApolloSequenceEntity(BaseEntity):
    """Schema for Apollo sequence (email campaign) entities.

    From POST /emailer_campaigns/search.
    """

    sequence_id: str = AirweaveField(
        ..., description="Apollo sequence/campaign ID.", is_entity_id=True
    )
    name: str = AirweaveField(..., description="Sequence name.", is_name=True, embeddable=True)
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the sequence was created.", is_created_at=True
    )
    active: Optional[bool] = AirweaveField(
        None, description="Whether the sequence is active.", embeddable=True
    )
    archived: Optional[bool] = Field(None, description="Whether the sequence is archived.")
    num_steps: Optional[int] = AirweaveField(
        None, description="Number of steps in the sequence.", embeddable=True
    )
    unique_scheduled: Optional[int] = Field(None, description="Count of scheduled emails.")
    unique_delivered: Optional[int] = Field(None, description="Count of delivered emails.")
    unique_opened: Optional[int] = Field(None, description="Count of opened emails.")
    unique_replied: Optional[int] = Field(None, description="Count of replies.")
    permissions: Optional[str] = Field(
        None, description="Sequence permissions (e.g. team_can_use)."
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this sequence in Apollo.",
        embeddable=False,
        unhashable=True,
    )

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_datetime_fields(cls, value: Any) -> Optional[datetime]:
        """Parse Apollo datetime (ISO string or None) to datetime."""
        return _parse_apollo_datetime(value)

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the web URL to view this sequence in Apollo, or empty string."""
        return self.web_url_value or ""


class ApolloEmailActivityEntity(BaseEntity):
    """Schema for Apollo email activity (outreach message) entities.

    From GET /emailer_messages/search. Represents emails sent as part of sequences.
    """

    message_id: str = AirweaveField(
        ..., description="Apollo emailer message ID.", is_entity_id=True
    )
    name: str = AirweaveField(
        ...,
        description="Display name (subject or 'Email to recipient').",
        is_name=True,
        embeddable=True,
    )
    subject: Optional[str] = AirweaveField(None, description="Email subject line.", embeddable=True)
    status: Optional[str] = AirweaveField(
        None, description="Status (e.g. delivered, scheduled, failed).", embeddable=True
    )
    from_email: Optional[str] = AirweaveField(None, description="Sender email.", embeddable=True)
    from_name: Optional[str] = AirweaveField(
        None, description="Sender display name.", embeddable=True
    )
    to_email: Optional[str] = AirweaveField(None, description="Recipient email.", embeddable=True)
    to_name: Optional[str] = AirweaveField(
        None, description="Recipient display name.", embeddable=True
    )
    body_text: Optional[str] = AirweaveField(
        None, description="Plain-text body (searchable).", embeddable=True
    )
    campaign_name: Optional[str] = AirweaveField(
        None, description="Sequence/campaign name.", embeddable=True
    )
    emailer_campaign_id: Optional[str] = Field(None, description="Apollo sequence ID.")
    contact_id: Optional[str] = Field(None, description="Apollo contact ID.")
    account_id: Optional[str] = Field(None, description="Apollo account ID.")
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the message was created.", is_created_at=True
    )
    completed_at: Optional[datetime] = AirweaveField(
        None, description="When the email was delivered.", is_updated_at=True
    )
    due_at: Optional[datetime] = AirweaveField(
        None, description="Scheduled send time.", embeddable=True
    )
    failure_reason: Optional[str] = AirweaveField(
        None, description="Reason for failure if status is failed.", embeddable=True
    )
    not_sent_reason: Optional[str] = AirweaveField(
        None, description="Reason email was not sent.", embeddable=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view this email in Apollo.",
        embeddable=False,
        unhashable=True,
    )

    @field_validator("created_at", "completed_at", "due_at", mode="before")
    @classmethod
    def parse_datetime_fields(cls, value: Any) -> Optional[datetime]:
        """Parse Apollo datetime (ISO string or None) to datetime."""
        return _parse_apollo_datetime(value)

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Return the web URL to view this email in Apollo, or empty string."""
        return self.web_url_value or ""
