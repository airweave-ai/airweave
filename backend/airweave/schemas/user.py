"""User schema module."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from airweave.schemas.organization import Organization


class UserOrganizationBase(BaseModel):
    """Base schema for UserOrganization relationship."""

    role: str = "member"  # owner, admin, member
    is_primary: bool = False
    user_id: UUID
    organization_id: UUID

    model_config = ConfigDict(from_attributes=True)


class UserOrganization(UserOrganizationBase):
    """Schema for UserOrganization relationship with full organization details."""

    organization: Organization

    model_config = ConfigDict(from_attributes=True)


class UserBase(BaseModel):
    """Base schema for User."""

    email: EmailStr
    full_name: Optional[str] = "Superuser"

    model_config = ConfigDict(from_attributes=True)


class UserCreate(UserBase):
    """Schema for creating a User object."""

    auth0_id: Optional[str] = None


class UserUpdate(BaseModel):
    """Schema for updating a User object."""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    auth0_id: Optional[str] = None
    permissions: Optional[list[str]] = None
    last_active_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserInDBBase(UserBase):
    """Base schema for User stored in DB."""

    id: UUID
    auth0_id: Optional[str] = None
    primary_organization_id: Optional[UUID] = None
    user_organizations: list[UserOrganization] = Field(default_factory=list)
    is_admin: bool = False
    is_superuser: bool = False
    last_active_at: Optional[datetime] = None

    @field_validator("user_organizations", mode="before")
    @classmethod
    def load_organizations(cls, v):
        """Ensure organizations are always loaded."""
        return v or []

    @property
    def primary_organization(self) -> Optional[UserOrganization]:
        """Get the primary organization for this user."""
        for org in self.user_organizations:
            if org.is_primary:
                return org
        return None

    @property
    def organization_roles(self) -> dict[UUID, str]:
        """Get a mapping of organization IDs to roles."""
        return {org.organization.id: org.role for org in self.user_organizations}

    model_config = ConfigDict(from_attributes=True)


class User(UserInDBBase):
    """Schema for User."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UserInDB(UserInDBBase):
    """Schema for User stored in DB."""

    hashed_password: Optional[str] = None


class UserWithOrganizations(UserInDBBase):
    """Schema for User with Organizations - now redundant as all users include orgs."""

    pass
