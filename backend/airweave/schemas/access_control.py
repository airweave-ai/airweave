"""Access control schemas for API."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class AccessControlMembershipCreate(BaseModel):
    """Schema for creating membership.

    Clean tuple design: (member_id, member_type) → group_id
    """

    member_id: str
    member_type: str  # "user" or "group"
    group_id: str
    group_name: Optional[str] = None


class AccessControlMembership(AccessControlMembershipCreate):
    """Schema for membership (with DB fields)."""

    id: UUID
    organization_id: UUID
    source_name: str
    source_connection_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
