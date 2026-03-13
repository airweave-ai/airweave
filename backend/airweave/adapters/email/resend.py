"""Resend email adapter.

Wraps the existing email.services functions behind the EmailService protocol.
All Resend-specific logic (rate limiting, retries, threading) stays in
email.services — this adapter is a thin delegation layer.
"""

from typing import Optional

from airweave.core.protocols.email import EmailService
from airweave.email.services import send_email_via_resend, send_welcome_email


class ResendEmailService(EmailService):
    """Production email adapter backed by Resend."""

    async def send(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        *,
        from_email: Optional[str] = None,
        scheduled_at: Optional[str] = None,
    ) -> bool:
        """Send an email via Resend with rate limiting and retries."""
        return await send_email_via_resend(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            from_email=from_email,
            scheduled_at=scheduled_at,
        )

    async def send_welcome(self, to_email: str, user_name: str) -> None:
        """Send welcome + follow-up emails via Resend."""
        await send_welcome_email(to_email, user_name)
