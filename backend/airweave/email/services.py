"""Email service for sending emails via Resend."""

import asyncio
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import resend

from airweave.core.config import settings
from airweave.core.logging import logger

# Rate limiter: Track last request time to respect Resend's 2 req/sec limit
_last_request_time = 0.0
_rate_limit_lock = asyncio.Lock()


async def _wait_for_rate_limit() -> None:
    """Ensure we don't exceed Resend's rate limit of 2 requests per second.

    This adds a minimum delay of 0.5 seconds between requests.
    """
    global _last_request_time

    async with _rate_limit_lock:
        now = time.monotonic()
        time_since_last_request = now - _last_request_time
        min_interval = 0.5  # 2 requests per second = 0.5 seconds minimum between requests

        if time_since_last_request < min_interval:
            sleep_time = min_interval - time_since_last_request
            await asyncio.sleep(sleep_time)

        _last_request_time = time.monotonic()


def _send_email_via_resend_sync(
    to_email: str,
    subject: str,
    html_body: str,
    from_email: Optional[str] = None,
    scheduled_at: Optional[str] = None,
) -> None:
    """Synchronous email sending function via Resend to be run in a thread pool.

    Args:
    ----
        to_email (str): Recipient email address
        subject (str): Email subject line
        html_body (str): HTML email body
        from_email (Optional[str]): Sender email (defaults to settings.RESEND_FROM_EMAIL)
        scheduled_at (Optional[str]): ISO 8601 timestamp for scheduled delivery

    """
    resend.api_key = settings.RESEND_API_KEY

    email_data = {
        "from": from_email or settings.RESEND_FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }

    if scheduled_at:
        email_data["scheduled_at"] = scheduled_at

    resend.Emails.send(email_data)


async def send_email_via_resend(
    to_email: str,
    subject: str,
    html_body: str,
    from_email: Optional[str] = None,
    scheduled_at: Optional[str] = None,
    max_retries: int = 3,
) -> bool:
    """Send an email via Resend asynchronously with rate limiting and retry logic.

    Args:
    ----
        to_email (str): Recipient email address
        subject (str): Email subject line
        html_body (str): HTML email body
        from_email (Optional[str]): Sender email (defaults to settings.RESEND_FROM_EMAIL)
        scheduled_at (Optional[str]): ISO 8601 timestamp for scheduled delivery
        max_retries (int): Maximum number of retry attempts for rate limit errors (default: 3)

    Returns:
    -------
        bool: True if email was sent successfully, False otherwise

    """
    if not settings.RESEND_API_KEY or not settings.RESEND_FROM_EMAIL:
        logger.debug("RESEND_API_KEY or RESEND_FROM_EMAIL not configured - skipping email")
        return False

    for attempt in range(max_retries + 1):
        # Apply rate limiting before each attempt (including retries)
        await _wait_for_rate_limit()

        try:
            await asyncio.to_thread(
                _send_email_via_resend_sync,
                to_email,
                subject,
                html_body,
                from_email,
                scheduled_at,
            )
            logger.info(f"Email sent to {to_email}: {subject}")
            return True
        except Exception as e:
            error_msg = str(e)

            # Check if it's a rate limit error
            is_rate_limit = "Too many requests" in error_msg or "rate limit" in error_msg.lower()

            if is_rate_limit and attempt < max_retries:
                # Exponential backoff: 1s, 2s, 4s
                backoff_time = 2**attempt
                logger.warning(
                    f"Rate limit hit sending email to {to_email}. "
                    f"Retrying in {backoff_time}s (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(backoff_time)
                continue

            # Either not a rate limit error, or we've exhausted retries
            logger.error(f"Failed to send email to {to_email} after {attempt + 1} attempts: {e}")
            return False

    return False


def _send_welcome_email_sync(to_email: str, user_name: str) -> None:
    """Synchronous email sending function to be run in a thread pool."""
    resend.api_key = settings.RESEND_API_KEY

    # Generate random delay between 10 and 40 minutes
    delay_minutes = random.randint(10, 40)

    # Calculate scheduled time using ISO 8601 format
    scheduled_time = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
    scheduled_at = scheduled_time.isoformat()

    resend.Emails.send(
        {
            "from": settings.RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": "Welcome to Airweave",
            "scheduled_at": scheduled_at,
            "html": """
<div style="font-family: Arial, sans-serif; font-size: 10pt;">
    <p style="margin: 0 0 15px 0;">
        Hey,
    </p>

    <p style="margin: 0 0 15px 0;">
        Thanks for signing up, this is Lennert (co-founder at Airweave).
    </p>

    <p style="margin: 0 0 15px 0;">
        Here's some useful stuff to get you started:
    </p>

    <p style="margin: 0 0 8px 0;">
        • Our docs: <a href="https://docs.airweave.ai/welcome"
          style="color: #0000EE; text-decoration: underline;">https://docs.airweave.ai/welcome</a>
    </p>
    <p style="margin: 0 0 8px 0;">
        • Our repo: <a href="https://github.com/airweave-ai/airweave"
          style="color: #0000EE; text-decoration: underline;">https://github.com/airweave-ai/airweave</a>
    </p>
    <p style="margin: 0 0 15px 0;">
        • Our discord: <a href="https://discord.com/invite/6wDWUhhuu2"
          style="color: #0000EE; text-decoration: underline;">https://discord.com/invite/6wDWUhhuu2</a>
    </p>

    <p style="margin: 15px 0;">
        Let me know if you need anything or have any questions.
    </p>

    <p style="margin: 15px 0 0 0;">
        Btw, if you want to see Airweave in action or just chat about what you're building,
        feel free to book some time with me here:
        <a href="https://cal.com/lennert-airweave/airweave-demo"
          style="color: #0000EE; text-decoration: underline;">https://cal.com/lennert-airweave/airweave-demo</a>
    </p>

    <p style="margin: 15px 0 0 0;">
        Lennert<br>
    </p>
</div>
            """,
        }
    )


def _send_welcome_followup_email_sync(to_email: str, user_name: str) -> None:
    """Synchronous follow-up email sending function to be run in a thread pool."""
    resend.api_key = settings.RESEND_API_KEY

    # Generate random delay between 30 and 60 minutes
    delay_minutes = random.randint(30, 60)

    # Schedule for 5 days from now plus random delay
    scheduled_time = datetime.now(timezone.utc) + timedelta(days=5, minutes=delay_minutes)
    scheduled_at = scheduled_time.isoformat()

    resend.Emails.send(
        {
            "from": settings.RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": "how's your Airweave setup going?",
            "scheduled_at": scheduled_at,
            "html": """
<div style="font-family: Arial, sans-serif; font-size: 10pt;">
    <p style="margin: 0 0 15px 0;">
        Hey, just checking in.
    </p>

    <p style="margin: 0 0 15px 0;">
        Saw you signed up and wanted to see how things are going with Airweave.
        Have you had the chance to run a query yet?
    </p>

      <p style="margin: 0 0 15px 0;">
        Would love to hear what you're building, and let me know if there's
        anything I can do to help.
    </p>

    <p style="margin: 15px 0 0 0;">
        Lennert (co-founder at Airweave)
    </p>

    <p style="margin: 15px 0 0 0;">

    </p>
</div>
            """,
        }
    )


async def send_welcome_followup_email(to_email: str, user_name: str) -> None:
    """Send a follow-up welcome email to a user 5 days after signup.

    Only works when both RESEND_API_KEY and RESEND_FROM_EMAIL are configured (production only).
    Uses asyncio.to_thread() to avoid blocking the event loop.
    The email will be scheduled for delivery 5 days from now using ISO 8601 format.
    """
    if not settings.RESEND_API_KEY or not settings.RESEND_FROM_EMAIL:
        logger.debug(
            "RESEND_API_KEY or RESEND_FROM_EMAIL not configured - skipping follow-up email"
        )
        return

    try:
        # Offload the synchronous email sending to a thread pool to avoid blocking the event loop
        await asyncio.to_thread(_send_welcome_followup_email_sync, to_email, user_name)
        logger.info(f"Follow-up welcome email scheduled for {to_email} (5 days from now)")
    except Exception as e:
        logger.error(f"Failed to schedule follow-up welcome email for {to_email}: {e}")


async def send_welcome_email(to_email: str, user_name: str) -> None:
    """Send a welcome email to a new user with random scheduling between 10-40 minutes.

    Also schedules a follow-up email 5 days later.

    Only works when both RESEND_API_KEY and RESEND_FROM_EMAIL are configured (production only).
    Uses asyncio.to_thread() to avoid blocking the event loop.
    The email will be scheduled for delivery between 10 and 40 minutes from now
    using ISO 8601 format.
    """
    if not settings.RESEND_API_KEY or not settings.RESEND_FROM_EMAIL:
        logger.debug("RESEND_API_KEY or RESEND_FROM_EMAIL not configured - skipping welcome email")
        return

    try:
        # Offload the synchronous email sending to a thread pool to avoid blocking the event loop
        await asyncio.to_thread(_send_welcome_email_sync, to_email, user_name)
        logger.info(f"Welcome email scheduled for {to_email}")

        # Also schedule the follow-up email
        await send_welcome_followup_email(to_email, user_name)
    except Exception as e:
        logger.error(f"Failed to schedule welcome email for {to_email}: {e}")
