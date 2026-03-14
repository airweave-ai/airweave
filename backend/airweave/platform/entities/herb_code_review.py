"""HERB Code Review entity schemas."""

from datetime import datetime
from typing import Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


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
