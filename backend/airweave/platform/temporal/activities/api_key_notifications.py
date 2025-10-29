"""Temporal activity for checking and notifying expiring API keys."""

from datetime import timedelta

from temporalio import activity

from airweave import crud
from airweave.core.config import settings
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.logging import logger
from airweave.db.session import get_db_context
from airweave.email.services import send_email_via_resend
from airweave.email.templates import get_api_key_expiration_email
from airweave.models.api_key import APIKey


async def _send_expiration_notification(
    api_key: APIKey,
    threshold_name: str,
    days_until_exp: int,
) -> bool:
    """Send expiration notification email for a single API key.

    Args:
    ----
        api_key (APIKey): The API key object
        threshold_name (str): Type of notification (14_days, 3_days, expired)
        days_until_exp (int): Days until expiration

    Returns:
    -------
        bool: True if notification sent successfully, False otherwise

    """
    # Skip if no creator email (API key auth created keys)
    if not api_key.created_by_email:
        return False

    # Generate email content
    settings_url = (
        f"{settings.APP_FULL_URL}/organization/settings?tab=api-keys"
        if settings.APP_FULL_URL
        else "https://app.airweave.ai/organization/settings?tab=api-keys"
    )

    api_key_preview = api_key.id.hex[:4]  # First 4 chars of UUID

    subject, html_body = get_api_key_expiration_email(
        days_until_expiration=days_until_exp,
        api_key_preview=api_key_preview,
        settings_url=settings_url,
    )

    # Send email
    success = await send_email_via_resend(
        to_email=api_key.created_by_email,
        subject=subject,
        html_body=html_body,
        from_email="info@airweave.ai",
    )

    if success:
        # Audit log: Notification sent (flows to Azure LAW)
        audit_logger = logger.with_context(event_type="api_key_expiration_notification_sent")
        audit_logger.info(
            f"API key expiration notification sent: {threshold_name} for key {api_key_preview} "
            f"to {api_key.created_by_email} (org={api_key.organization_id}, "
            f"days_until_expiration={days_until_exp}, "
            f"expires={api_key.expiration_date.isoformat()})"
        )

    return success


@activity.defn
async def check_and_notify_expiring_keys_activity() -> dict[str, int]:
    """Check for expiring API keys and send notification emails.

    This activity:
    1. Queries the database for keys expiring in 14 days, 3 days, or already expired
    2. Sends appropriate notification emails to the key creators
    3. Returns counts of notifications sent by type

    Returns:
    -------
        dict[str, int]: Counts of notifications sent
            (e.g., {"14_days": 2, "3_days": 1, "expired": 0})

    """
    logger.info("Starting API key expiration check")

    now = utc_now_naive()
    notification_counts = {
        "14_days": 0,
        "3_days": 0,
        "expired": 0,
        "errors": 0,
    }

    # Define notification thresholds
    thresholds = [
        ("14_days", now + timedelta(days=14), now + timedelta(days=15)),  # 14-15  days window
        ("3_days", now + timedelta(days=3), now + timedelta(days=4)),  # 3-4 days window
        ("expired", now - timedelta(hours=24), now),  # Recently expired (last 2h)
    ]

    async with get_db_context() as db:
        for threshold_name, start_date, end_date in thresholds:
            try:
                # Query API keys expiring in this window using CRUD layer
                api_keys = await crud.api_key.get_keys_expiring_in_range(
                    db=db,
                    start_date=start_date,
                    end_date=end_date,
                )

                logger.info(
                    f"Found {len(api_keys)} API keys for {threshold_name} notification threshold"
                )

                for api_key in api_keys:
                    try:
                        # Calculate days until expiration
                        days_until_exp = (api_key.expiration_date - now).days

                        # Send notification using helper function
                        success = await _send_expiration_notification(
                            api_key=api_key,
                            threshold_name=threshold_name,
                            days_until_exp=days_until_exp,
                        )

                        if success:
                            notification_counts[threshold_name] += 1
                        else:
                            notification_counts["errors"] += 1

                    except Exception as e:
                        logger.error(
                            f"Failed to send notification for API key {api_key.id}: {e}",
                            exc_info=True,
                        )
                        notification_counts["errors"] += 1

            except Exception as e:
                logger.error(f"Failed to process {threshold_name} threshold: {e}", exc_info=True)
                notification_counts["errors"] += 1

    logger.info(f"API key expiration check complete: {notification_counts}")
    return notification_counts
