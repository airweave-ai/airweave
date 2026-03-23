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
        description="Number of days until the API key expires (default: 90, max: 180)",
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
            return 90

        if v < 1:
            raise ValueError("Expiration days must be at least 1.")
        if v > 180:
            raise ValueError("Expiration days cannot be more than 180.")
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
    last_used_ip: Optional[str] = None
    expiration_date: datetime
    status: str = "active"
    revoked_at: Optional[datetime] = None
    key_prefix: Optional[str] = None
    created_by_email: Optional[EmailStr] = None
    modified_by_email: Optional[EmailStr] = None

    model_config = ConfigDict(from_attributes=True)


class APIKey(APIKeyInDBBase):
    """Schema for API keys returned to clients - includes decrypted key."""

    decrypted_key: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class APIKeyUsageLogEntry(BaseModel):
    """Single usage log entry for an API key."""

    id: UUID
    api_key_id: Optional[UUID] = None
    organization_id: UUID
    timestamp: datetime
    ip_address: str
    endpoint: str
    user_agent: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class APIKeyUsageStats(BaseModel):
    """Aggregated usage statistics for an API key."""

    api_key_id: UUID
    total_requests: int
    first_used: Optional[datetime] = None
    last_used: Optional[datetime] = None
    unique_ips: int = 0
    unique_endpoints: int = 0

    model_config = ConfigDict(from_attributes=True)
