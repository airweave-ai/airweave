"""
Pipedrive entity schemas.

Based on the Pipedrive API (read-only scope), we define entity schemas for
the major Pipedrive objects relevant to our application:
 - Deal
 - Organization

Objects that reference a hierarchical relationship (e.g., deals linked to organizations)
will represent that hierarchy through a list of breadcrumbs (see Breadcrumb in
airweave.platform.entities._base) rather than nested objects.

References:
    https://developers.pipedrive.com/docs/api/v1/Deals
    https://developers.pipedrive.com/docs/api/v1/Organizations
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._base import Breadcrumb, ChunkEntity


class PipedriveOrganizationEntity(ChunkEntity):
    """Schema for a Pipedrive organization.

    See:
      https://developers.pipedrive.com/docs/api/v1/Organizations
    """

    name: str = Field(..., description="Name of the organization.")
    address: Optional[str] = Field(None, description="Full address of the organization.")
    address_country: Optional[str] = Field(None, description="Country part of the organization's address.")
    people_count: Optional[int] = Field(None, description="Number of people associated with this organization.")
    open_deals_count: Optional[int] = Field(None, description="Number of open deals associated with this organization.")
    closed_deals_count: Optional[int] = Field(None, description="Number of closed deals associated with this organization.")
    owner_id: Optional[int] = Field(None, description="ID of the user who owns this organization.")
    created_at: Optional[datetime] = Field(None, description="Timestamp when the organization was created.")
    updated_at: Optional[datetime] = Field(None, description="Timestamp when the organization was last updated.")


class PipedriveDealEntity(ChunkEntity):
    """Schema for a Pipedrive deal.

    See:
      https://developers.pipedrive.com/docs/api/v1/Deals
    """

    breadcrumbs: List[Breadcrumb] = Field(
        default_factory=list,
        description="Breadcrumb hierarchy (e.g., parent organization or person).",
    )
    title: Optional[str] = Field(None, description="Title of the deal.")
    value: Optional[float] = Field(None, description="Value of the deal (in the account's default currency).")
    currency: Optional[str] = Field(None, description="Currency of the deal value.")
    status: Optional[str] = Field(None, description="Status of the deal (e.g., 'open', 'won', 'lost').")
    stage_id: Optional[int] = Field(None, description="ID of the pipeline stage this deal is in.")
    pipeline_id: Optional[int] = Field(None, description="ID of the pipeline this deal belongs to.")
    probability: Optional[float] = Field(None, description="Probability of the deal closing (percentage, 0-100).")
    expected_close_date: Optional[datetime] = Field(None, description="Expected close date of the deal.")
    org_id: Optional[int] = Field(None, description="ID of the organization associated with this deal.")
    person_id: Optional[int] = Field(None, description="ID of the person associated with this deal.")
    owner_id: Optional[int] = Field(None, description="ID of the user who owns this deal.")
    creator_user_id: Optional[int] = Field(None, description="ID of the user who created this deal.")
    has_activities: Optional[bool] = Field(
        False, description="Indicates if the deal has associated activities."
    )
    activities_count: Optional[int] = Field(None, description="Number of activities associated with this deal.")
    notes_count: Optional[int] = Field(None, description="Number of notes associated with this deal.")
    created_at: Optional[datetime] = Field(None, description="Timestamp when the deal was created.")
    updated_at: Optional[datetime] = Field(None, description="Timestamp when the deal was last updated.")
    add_time: Optional[datetime] = Field(None, description="Timestamp when the deal was added to Pipedrive.")
    won_time: Optional[datetime] = Field(None, description="Timestamp when the deal was marked as won, if applicable.")
    lost_time: Optional[datetime] = Field(None, description="Timestamp when the deal was marked as lost, if applicable.")