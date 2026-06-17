"""Response schemas for user session management."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UserSessionRead(BaseModel):
    """Public representation of a user session."""

    id: UUID
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    last_active_at: Optional[datetime] = None
    is_current: bool = False

    model_config = ConfigDict(from_attributes=True)


class SessionTerminationResult(BaseModel):
    """Result of a session termination operation."""

    terminated_count: int
    terminated_at: datetime
