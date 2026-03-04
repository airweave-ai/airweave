"""APIKey schema."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class APIKeyBase(BaseModel):
    """Base schema for APIKey."""

    model_config = ConfigDict(from_attributes=True)


class APIKeyCreate(BaseModel):
    """Schema for creating an APIKey object."""

    expiration_days: Optional[int] = Field(
        default=90,
        description="Number of days until the API key expires (default: 90, max: 365)",
    )

    @field_validator("expiration_days")
    def check_expiration_days(cls, v: Optional[int]) -> Optional[int]:
        """Validate the expiration days.

        Args:
        ----
            v (int): The number of days until expiration.

        Raises:
        ------
            ValueError: If the expiration days is invalid.

        Returns:
        -------
            int: The validated expiration days.

        """
        if v is None:
            return 90  # Default to 90 days

        if v < 1:
            raise ValueError("Expiration days must be at least 1.")
        if v > 365:
            raise ValueError("Expiration days cannot be more than 365.")
        return v

    model_config = ConfigDict(from_attributes=True)


class APIKeyUpdate(BaseModel):
    """Schema for updating an APIKey object."""

    expiration_date: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class APIKeyInDBBase(APIKeyBase):
    """Base schema for APIKey stored in DB."""

    id: UUID
    organization_id: UUID
    created_at: datetime
    modified_at: datetime
    last_used_date: Optional[datetime] = None
    expiration_date: datetime
    created_by_email: Optional[EmailStr] = None
    modified_by_email: Optional[EmailStr] = None

    model_config = ConfigDict(from_attributes=True)


class APIKey(APIKeyInDBBase):
    """Schema for API keys returned to clients - includes decrypted key."""

    decrypted_key: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
