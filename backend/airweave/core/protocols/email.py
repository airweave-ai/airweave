"""Email service protocol.

Abstracts the external email provider (Resend, etc.) so domain code
never imports infrastructure directly. Adapters implement this protocol;
domains depend only on the protocol type.
"""

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class EmailService(Protocol):
    """External email delivery system (Resend, etc.).

    The NullEmailService adapter provides no-ops for environments
    without email configuration (local dev, CI, self-hosted).
    """

    async def send(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        *,
        from_email: Optional[str] = None,
        scheduled_at: Optional[str] = None,
    ) -> bool:
        """Send an email.

        Args:
            to_email: Recipient email address.
            subject: Email subject line.
            html_body: HTML email body.
            from_email: Sender email (defaults to provider default).
            scheduled_at: ISO 8601 timestamp for scheduled delivery.

        Returns:
            True if accepted for delivery, False on failure.
        """
        ...

    async def send_welcome(self, to_email: str, user_name: str) -> None:
        """Send a welcome email to a newly created user.

        Best-effort: implementations should log errors but never raise.
        May also schedule follow-up emails.
        """
        ...
