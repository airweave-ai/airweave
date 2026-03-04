"""Model for tracking processed Stripe webhook events for idempotency."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from airweave.models._base import Base


class ProcessedWebhookEvent(Base):
    """Tracks Stripe event IDs that have been successfully processed.

    Used for webhook idempotency: if an event ID exists in this table,
    the webhook handler skips processing and returns 200 immediately.
    """

    __tablename__ = "processed_webhook_event"

    stripe_event_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
