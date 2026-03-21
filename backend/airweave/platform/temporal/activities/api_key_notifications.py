"""Temporal activity for checking and notifying expiring API keys."""

from dataclasses import dataclass
from datetime import timedelta

from temporalio import activity

from airweave import crud
from airweave.core.config import settings
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.logging import logger
from airweave.core.protocols.email import EmailService
from airweave.db.session import get_db_context
from airweave.email.templates import get_api_key_expiration_email
from airweave.models.api_key import APIKey


@dataclass
class CheckAndNotifyExpiringKeysActivity:
    """Check for expiring API keys and send notification emails."""

    email_service: EmailService

    async def _send_expiration_notification(
        self,
        api_key: APIKey,
        threshold_name: str,
        days_until_exp: int,
    ) -> bool:
        if not api_key.created_by_email:
            return False

        settings_url = (
            f"{settings.APP_FULL_URL}/organization/settings?tab=api-keys"
            if settings.APP_FULL_URL
            else "https://app.airweave.ai/organization/settings?tab=api-keys"
        )

        api_key_preview = api_key.id.hex[:4]

        subject, html_body = get_api_key_expiration_email(
            days_until_expiration=days_until_exp,
            api_key_preview=api_key_preview,
            settings_url=settings_url,
        )

        success = await self.email_service.send(
            to_email=api_key.created_by_email,
            subject=subject,
            html_body=html_body,
            from_email="info@airweave.ai",
        )

        if success:
            audit_logger = logger.with_context(event_type="api_key_expiration_notification_sent")
            audit_logger.info(
                f"API key expiration notification sent: {threshold_name} "
                f"for key {api_key_preview} to {api_key.created_by_email} "
                f"(org={api_key.organization_id}, "
                f"days_until_expiration={days_until_exp}, "
                f"expires={api_key.expiration_date.isoformat()})"
            )

        return success

    @activity.defn(name="check_and_notify_expiring_keys_activity")
    async def run(self) -> dict[str, int]:
        """Scan for expiring API keys and send notification emails."""
        logger.info("Starting API key expiration check")

        now = utc_now_naive()
        notification_counts: dict[str, int] = {
            "14_days": 0,
            "3_days": 0,
            "expired": 0,
            "errors": 0,
        }

        thresholds = [
            ("14_days", now + timedelta(days=14), now + timedelta(days=15)),
            ("3_days", now + timedelta(days=3), now + timedelta(days=4)),
            ("expired", now - timedelta(hours=24), now),
        ]

        async with get_db_context() as db:
            for threshold_name, start_date, end_date in thresholds:
                try:
                    api_keys = await crud.api_key.get_keys_expiring_in_range(
                        db=db,
                        start_date=start_date,
                        end_date=end_date,
                    )

                    logger.info(
                        f"Found {len(api_keys)} API keys for "
                        f"{threshold_name} notification threshold"
                    )

                    for api_key in api_keys:
                        try:
                            days_until_exp = (api_key.expiration_date - now).days

                            success = await self._send_expiration_notification(
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
                    logger.error(
                        f"Failed to process {threshold_name} threshold: {e}", exc_info=True
                    )
                    notification_counts["errors"] += 1

        logger.info(f"API key expiration check complete: {notification_counts}")
        return notification_counts
