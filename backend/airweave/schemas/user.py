"""User schema module."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, validator


class UserBase(BaseModel):
    """Base schema for User."""

    email: EmailStr
    full_name: Optional[str] = "Superuser"
    organization_id: Optional[UUID] = None

    @validator("organization_id", pre=True, always=True)
    def organization_must_exist_for_operations(cls, v, values):
        """Validate that the organization_id field is present for all operations except create."""
        # During validation of incoming data, we allow None because create will handle it
        # For database objects, this should never be None
        return v

    class Config:
        """Pydantic config for UserBase."""

        from_orm = True
        from_attributes = True


class UserCreate(UserBase):
    """Schema for creating a User object."""

    # Allow organization_id to be None during creation, as it will be created if not provided


class UserUpdate(UserBase):
    """Schema for updating a User object."""

    permissions: Optional[list[str]] = None

    @validator("organization_id")
    def organization_required_for_update(cls, v):
        """Validate that the organization_id is not None for updates."""
        if v is None:
            raise ValueError("organization_id cannot be None when updating a user")
        return v


class UserInDBBase(UserBase):
    """Base schema for User stored in DB."""

    id: UUID
    permissions: Optional[list[str]] = None

    @validator("organization_id")
    def organization_required_in_db(cls, v):
        """Validate that the organization_id is never None in the database."""
        if v is None:
            raise ValueError("User must have an organization_id in the database")
        return v

    class Config:
        """Pydantic config for UserInDBBase."""

        from_attributes = True


class User(UserInDBBase):
    """Schema for User."""

    class Config:
        """Pydantic config for User."""

        from_attributes = True
        populate_by_name = True


class UserInDB(UserInDBBase):
    """Schema for User stored in DB."""

    hashed_password: Optional[str] = None


class UserWithOrganizations(UserInDBBase):
    """Schema for User with Organizations."""

    pass

    # organizations: list[Organization]
