"""Sync schemas."""

import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from airweave import schemas
from airweave.core.shared_models import SyncStatus
from airweave.platform.sync.config.base import SyncConfig


class SyncBase(BaseModel):
    """Base schema for Sync."""

    name: str
    source_connection_id: UUID  # system connection id
    destination_connection_ids: list[UUID]
    description: Optional[str] = None
    cron_schedule: Optional[str] = None  # Full sync schedule (hourly/daily/weekly)
    next_scheduled_run: Optional[datetime] = None
    temporal_schedule_id: Optional[str] = None
    sync_type: str = "full"
    sync_metadata: Optional[dict] = None
    sync_config: Optional[SyncConfig] = None
    status: Optional[SyncStatus] = SyncStatus.ACTIVE

    @field_validator("cron_schedule")
    def validate_cron_schedule(cls, v: str) -> str:
        """Validate cron schedule format for full syncs.

        Format: * * * * *
        minute (0-59)
        hour (0-23)
        day of month (1-31)
        month (1-12 or JAN-DEC)
        day of week (0-6 or SUN-SAT)

        * * * * *
        │ │ │ │ │
        │ │ │ │ └─ Day of week (0-6 or SUN-SAT)
        │ │ │ └─── Month (1-12 or JAN-DEC)
        │ │ └───── Day of month (1-31)
        │ └─────── Hour (0-23)
        └───────── Minute (0-59)
        """
        if v is None:
            return None
        cron_pattern = r"^(\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-9]{1,2}|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|[0-9]{1,2}-[0-9]{1,2}|[0-9]{1,2}/[0-9]{1,2}|[0-9]{1,2},[0-9]{1,2}|\*\/[0-9]{1,2}) (\*|[0-6]|SUN|MON|TUE|WED|THU|FRI|SAT|[0-6]-[0-6]|[0-6]/[0-6]|[0-6],[0-6]|\*\/[0-6])$"  # noqa: E501
        if not re.match(cron_pattern, v):
            raise ValueError("Invalid cron schedule format")
        return v

    @field_validator("sync_type")
    def validate_sync_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate sync type."""
        if v is not None and v not in ["full", "incremental"]:
            raise ValueError("sync_type must be 'full' or 'incremental'")
        return v

    model_config = ConfigDict(from_attributes=True)


class SyncCreate(SyncBase):
    """Schema for creating a Sync object."""

    run_immediately: bool = False

    def to_base(self) -> SyncBase:
        """Convert to base schema."""
        return SyncBase(**self.model_dump(exclude={"run_immediately"}))


class SyncUpdate(BaseModel):
    """Schema for updating a Sync object."""

    name: Optional[str] = None
    cron_schedule: Optional[str] = None
    next_scheduled_run: Optional[datetime] = None
    sync_metadata: Optional[dict] = None
    sync_config: Optional[SyncConfig] = None
    status: Optional[SyncStatus] = None
    temporal_schedule_id: Optional[str] = None
    sync_type: Optional[str] = None

    @field_validator("sync_type")
    def validate_sync_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate sync type."""
        if v is not None and v not in ["full", "incremental"]:
            raise ValueError("sync_type must be 'full' or 'incremental'")
        return v


class MinuteLevelScheduleConfig(BaseModel):
    """Configuration for minute-level incremental sync schedules."""

    cron_expression: str = Field(
        default="*/1 * * * *",
        description="Minute-level cron expression for incremental sync (default: every minute)",
    )

    @field_validator("cron_expression")
    def validate_minute_level_cron(cls, v: str) -> str:
        """Validate cron expression for minute-level incremental sync."""
        # Allow minute-level patterns like */1, */5, */15, */30
        # Restrict minute values to 0-59 range
        minute_level_pattern = r"^(\*\/[1-5]?[0-9]|[0-5]?[0-9]) \* \* \* \*$"
        if not re.match(minute_level_pattern, v):
            raise ValueError(
                "Minute-level cron must be minute-level only "
                "(e.g., */1 * * * * for every minute) with valid minute values (0-59)"
            )
        return v


class ScheduleResponse(BaseModel):
    """Response for schedule operations."""

    schedule_id: str
    status: str
    message: str


class SyncInDBBase(SyncBase):
    """Base schema for Sync stored in DB."""

    id: UUID
    organization_id: UUID
    created_at: datetime
    modified_at: datetime
    created_by_email: Optional[EmailStr] = None
    modified_by_email: Optional[EmailStr] = None
    status: SyncStatus

    model_config = ConfigDict(from_attributes=True)


class Sync(SyncInDBBase):
    """Schema for Sync."""

    pass


class SyncWithoutConnections(BaseModel):
    """Schema for Sync without connections."""

    name: str
    description: Optional[str] = None
    cron_schedule: Optional[str] = None
    next_scheduled_run: Optional[datetime] = None
    status: SyncStatus
    sync_metadata: Optional[dict] = None
    sync_config: Optional[SyncConfig] = None
    temporal_schedule_id: Optional[str] = None
    sync_type: str = "full"
    id: UUID
    organization_id: UUID
    created_at: datetime
    modified_at: datetime
    created_by_email: Optional[EmailStr] = None
    modified_by_email: Optional[EmailStr] = None

    @field_validator("sync_type")
    def validate_sync_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate sync type."""
        if v is not None and v not in ["full", "incremental"]:
            raise ValueError("sync_type must be 'full' or 'incremental'")
        return v

    model_config = ConfigDict(from_attributes=True)


class SyncWithSourceConnection(SyncInDBBase):
    """Schema for Sync with source connection."""

    source_connection: Optional[schemas.Connection] = None
