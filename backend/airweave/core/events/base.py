"""Base class for all domain events.

Enforces that every event is a validated, frozen Pydantic model with
the three fields the EventBus protocol requires for routing and metadata.

The DomainEvent Protocol (core/protocols/event_bus.py) remains the bus's
structural contract. This base class is what event authors must inherit
from to guarantee Pydantic validation.
"""

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BaseDomainEvent(BaseModel):
    """Base for all domain events.

    Provides the three fields required by the DomainEvent protocol,
    frozen immutability, and Pydantic validation.

    Subclasses narrow event_type to a domain-specific str enum
    and add domain-specific fields.
    """

    model_config = ConfigDict(frozen=True)

    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: UUID

    def to_webhook_payload(self) -> dict:
        """Serialize to a JSON-safe dict for webhook delivery.

        Uses Pydantic's ``model_dump(mode="json")`` which automatically
        converts UUIDs to strings, datetimes to ISO format, and enums
        to their values.
        """
        return self.model_dump(mode="json")
