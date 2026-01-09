"""Schemas for organization invitations."""

from typing import Optional

from pydantic import BaseModel, EmailStr


class InvitationBase(BaseModel):
    """Base schema for invitations."""

    email: EmailStr
    role: str = "member"


class InvitationCreate(InvitationBase):
    """Schema for creating an invitation."""

    pass


class InvitationResponse(BaseModel):
    """Schema for invitation responses."""

    id: str
    email: str
    role: str
    status: str
    invited_at: Optional[str] = None


class MemberResponse(BaseModel):
    """Schema for organization member responses."""

    id: str
    email: str
    name: str
    role: str
    status: str = "active"
    is_primary: bool = False
    auth0_id: Optional[str] = None


class MemberRoleUpdate(BaseModel):
    """Schema for updating a member's role."""

    role: str  # "admin" or "member" (not "owner" - ownership transfer is separate)
