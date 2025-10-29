"""Email module for Airweave."""

from airweave.email.services import send_email_via_resend, send_welcome_email
from airweave.email.templates import get_api_key_expiration_email

__all__ = [
    "send_email_via_resend",
    "send_welcome_email",
    "get_api_key_expiration_email",
]
