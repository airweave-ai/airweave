"""Null email service — no-ops for environments without email config.

Used when RESEND_API_KEY is not set (local dev, CI, self-hosted).
"""

from typing import Optional

from airweave.core.protocols.email import EmailService


class NullEmailService(EmailService):
    """No-op email service for environments without email configuration."""

    async def send(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        *,
        from_email: Optional[str] = None,
        scheduled_at: Optional[str] = None,
    ) -> bool:
        """Return False (no-op)."""
        return False

    async def send_welcome(self, to_email: str, user_name: str) -> None:
        """Do nothing (no-op)."""
        pass
