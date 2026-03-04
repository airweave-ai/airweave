"""Base class for all domain events.

Enforces that every event is a validated, frozen Pydantic model with
the three fields the EventBus protocol requires for routing and metadata.
"""

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from airweave.core.events.enums import EventType


class DomainEvent(BaseModel):
    """Base for all domain events.

    Provides the three fields required by the event bus,
    frozen immutability, and Pydantic validation.

    Subclasses narrow event_type to a domain-specific enum
    (e.g. SyncEventType) and add domain-specific fields.
    """

    model_config = ConfigDict(frozen=True)

    event_type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID
