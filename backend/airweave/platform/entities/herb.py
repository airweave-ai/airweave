"""HERB benchmark entity schemas.

Entity types for the Salesforce HERB (Heterogeneous Enterprise RAG Benchmark)
dataset. Each entity type maps to one of HERB's artifact categories, with
`is_entity_id` fields matching HERB's artifact `id` values so that HERB's
citation IDs can be used directly as `relevant_entity_ids` in evals.
"""

from datetime import datetime
from typing import Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class HerbMessageEntity(BaseEntity):
    """Slack message from the HERB benchmark dataset."""

    message_id: str = AirweaveField(
        ...,
        description="HERB message ID (e.g. '20260421-0-921c4')",
        is_entity_id=True,
    )
    text: str = AirweaveField(
        ...,
        description="Message text content",
        is_name=True,
        embeddable=True,
    )
    sender_id: str = AirweaveField(
        ...,
        description="Sender user ID (e.g. 'eid_9b023657')",
        embeddable=True,
    )
    sender_name: Optional[str] = AirweaveField(
        None,
        description="Resolved sender name from employee directory",
        embeddable=True,
    )
    channel_name: str = AirweaveField(
        ...,
        description="Slack channel name",
        embeddable=True,
    )
    channel_id: str = AirweaveField(
        ...,
        description="Slack channel ID",
    )
    message_time: datetime = AirweaveField(
        ...,
        description="Message timestamp",
        is_created_at=True,
    )
    product_name: str = AirweaveField(
        ...,
        description="HERB product name this message belongs to",
        embeddable=True,
    )


class HerbDocumentEntity(BaseEntity):
    """Document (PRD, vision doc, system design, etc.) from the HERB benchmark dataset."""

    doc_id: str = AirweaveField(
        ...,
        description="HERB document ID (e.g. 'backaix_market_research_report')",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="Document title derived from ID",
        is_name=True,
        embeddable=True,
    )
    content: str = AirweaveField(
        ...,
        description="Full document content",
        embeddable=True,
    )
    doc_type: str = AirweaveField(
        ...,
        description="Document type (e.g. 'Market Research Report')",
        embeddable=True,
    )
    author_id: str = AirweaveField(
        ...,
        description="Author employee ID",
        embeddable=True,
    )
    author_name: Optional[str] = AirweaveField(
        None,
        description="Resolved author name from employee directory",
        embeddable=True,
    )
    feedback: Optional[str] = AirweaveField(
        None,
        description="Document feedback (present on ~200 of 400 docs)",
        embeddable=True,
    )
    document_link: Optional[str] = AirweaveField(
        None,
        description="Document URL (synthetic)",
    )
    doc_created_at: Optional[datetime] = AirweaveField(
        None,
        description="Document creation date",
        is_created_at=True,
    )
    product_name: str = AirweaveField(
        ...,
        description="HERB product name this document belongs to",
        embeddable=True,
    )


class HerbMeetingTranscriptEntity(BaseEntity):
    """Meeting transcript from the HERB benchmark dataset."""

    meeting_id: str = AirweaveField(
        ...,
        description="HERB meeting transcript ID",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="Meeting title (product + date)",
        is_name=True,
        embeddable=True,
    )
    transcript: str = AirweaveField(
        ...,
        description="Full meeting transcript with attendee names and dialogue",
        embeddable=True,
    )
    document_type: str = AirweaveField(
        ...,
        description="Document type classification",
        embeddable=True,
    )
    participant_ids: str = AirweaveField(
        ...,
        description="Comma-separated participant employee IDs",
        embeddable=True,
    )
    participant_names: Optional[str] = AirweaveField(
        None,
        description="Resolved participant names from employee directory",
        embeddable=True,
    )
    meeting_date: Optional[datetime] = AirweaveField(
        None,
        description="Meeting date",
        is_created_at=True,
    )
    product_name: str = AirweaveField(
        ...,
        description="HERB product name this meeting belongs to",
        embeddable=True,
    )


class HerbMeetingChatEntity(BaseEntity):
    """Meeting chat log from the HERB benchmark dataset."""

    chat_id: str = AirweaveField(
        ...,
        description="HERB meeting chat ID",
        is_entity_id=True,
    )
    text: str = AirweaveField(
        ...,
        description="Chat text content",
        is_name=True,
        embeddable=True,
    )
    product_name: str = AirweaveField(
        ...,
        description="HERB product name this chat belongs to",
        embeddable=True,
    )


class HerbPullRequestEntity(BaseEntity):
    """GitHub pull request from the HERB benchmark dataset."""

    pr_id: str = AirweaveField(
        ...,
        description="HERB PR ID (e.g. 'github_com_salesforce_backAIX_pull_1')",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="PR title",
        is_name=True,
        embeddable=True,
    )
    summary: str = AirweaveField(
        ...,
        description="PR summary/description",
        embeddable=True,
    )
    pr_link: str = AirweaveField(
        ...,
        description="PR URL (ground truth for PR-type questions)",
        embeddable=True,
    )
    state: str = AirweaveField(
        ...,
        description="PR state (open, closed, etc.)",
        embeddable=True,
    )
    merged: str = AirweaveField(
        ...,
        description="Whether PR is merged (string 'True'/'False' in HERB)",
        embeddable=True,
    )
    number: str = AirweaveField(
        ...,
        description="PR number",
        embeddable=True,
    )
    author_login: str = AirweaveField(
        ...,
        description="PR author login (eid_* or EMP_*)",
        embeddable=True,
    )
    reviews_text: Optional[str] = AirweaveField(
        None,
        description="Concatenated review comments with reviewer and state",
        embeddable=True,
    )
    pr_created_at: Optional[datetime] = AirweaveField(
        None,
        description="PR creation timestamp",
        is_created_at=True,
    )
    product_name: str = AirweaveField(
        ...,
        description="HERB product name this PR belongs to",
        embeddable=True,
    )


class HerbResourceEntity(BaseEntity):
    """Shared URL/bookmark from the HERB benchmark dataset."""

    resource_id: str = AirweaveField(
        ...,
        description="HERB resource ID",
        is_entity_id=True,
    )
    description: str = AirweaveField(
        ...,
        description="URL description",
        is_name=True,
        embeddable=True,
    )
    link: str = AirweaveField(
        ...,
        description="URL (ground truth for URL-type questions)",
        embeddable=True,
    )
    product_name: str = AirweaveField(
        ...,
        description="HERB product name this resource belongs to",
        embeddable=True,
    )


class HerbEmployeeEntity(BaseEntity):
    """Employee record from the HERB benchmark dataset."""

    employee_id: str = AirweaveField(
        ...,
        description="Employee ID (e.g. 'eid_9b023657')",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Employee full name",
        is_name=True,
        embeddable=True,
    )
    role: str = AirweaveField(
        ...,
        description="Job role/title",
        embeddable=True,
    )
    location: str = AirweaveField(
        ...,
        description="Office location",
        embeddable=True,
    )
    org: str = AirweaveField(
        ...,
        description="Organization unit",
        embeddable=True,
    )


class HerbCustomerEntity(BaseEntity):
    """Customer profile from the HERB benchmark dataset."""

    customer_id: str = AirweaveField(
        ...,
        description="Customer ID (e.g. 'CUST-0001')",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Customer full name",
        is_name=True,
        embeddable=True,
    )
    role: str = AirweaveField(
        ...,
        description="Customer role/title",
        embeddable=True,
    )
    company: str = AirweaveField(
        ...,
        description="Customer company name",
        embeddable=True,
    )
