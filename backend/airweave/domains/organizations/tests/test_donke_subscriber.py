"""Tests for the DonkeNotificationSubscriber.

Verifies:
- Skips when DONKE_URL or DONKE_API_KEY is not set
- Skips non-created events (deleted, member_added, etc.)
- Failure is swallowed (best-effort, never crashes the bus)
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from airweave.core.events.organization import OrganizationLifecycleEvent
from airweave.domains.organizations.subscribers.donke_notification import (
    DonkeNotificationSubscriber,
)

ORG_ID = uuid4()


class TestDonkeSkipConditions:
    @pytest.mark.asyncio
    @patch("airweave.domains.organizations.subscribers.donke_notification.settings")
    async def test_skips_when_donke_url_missing(self, mock_settings):
        mock_settings.DONKE_URL = ""
        mock_settings.DONKE_API_KEY = "some-key"

        sub = DonkeNotificationSubscriber()
        event = OrganizationLifecycleEvent.created(
            organization_id=ORG_ID, organization_name="X", owner_email="x@x.com",
        )

        # Should not raise, should not make HTTP call
        await sub.handle(event)

    @pytest.mark.asyncio
    @patch("airweave.domains.organizations.subscribers.donke_notification.settings")
    async def test_skips_when_donke_api_key_missing(self, mock_settings):
        mock_settings.DONKE_URL = "https://donke.example.com"
        mock_settings.DONKE_API_KEY = ""

        sub = DonkeNotificationSubscriber()
        event = OrganizationLifecycleEvent.created(
            organization_id=ORG_ID, organization_name="X", owner_email="x@x.com",
        )

        await sub.handle(event)

    @pytest.mark.asyncio
    @patch("airweave.domains.organizations.subscribers.donke_notification.settings")
    async def test_skips_non_created_events(self, mock_settings):
        mock_settings.DONKE_URL = "https://donke.example.com"
        mock_settings.DONKE_API_KEY = "key-123"

        sub = DonkeNotificationSubscriber()

        deleted_event = OrganizationLifecycleEvent.deleted(
            organization_id=ORG_ID, organization_name="Doomed",
        )
        # Should not make HTTP call for deleted events
        await sub.handle(deleted_event)

        member_event = OrganizationLifecycleEvent.member_added(
            organization_id=ORG_ID,
        )
        await sub.handle(member_event)


class TestDonkeHttpCall:
    @pytest.mark.asyncio
    @patch("airweave.domains.organizations.subscribers.donke_notification.settings")
    @patch("airweave.domains.organizations.subscribers.donke_notification.httpx.AsyncClient")
    async def test_sends_correct_payload(self, mock_client_cls, mock_settings):
        mock_settings.DONKE_URL = "https://donke.example.com"
        mock_settings.DONKE_API_KEY = "key-123"

        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        sub = DonkeNotificationSubscriber()
        event = OrganizationLifecycleEvent.created(
            organization_id=ORG_ID, organization_name="Acme",
            owner_email="boss@acme.com", plan="pro",
        )

        await sub.handle(event)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "notify-signup" in call_args[0][0]
        payload = call_args[1]["json"]
        assert payload["organization_name"] == "Acme"
        assert payload["user_email"] == "boss@acme.com"
        assert payload["plan"] == "pro"

    @pytest.mark.asyncio
    @patch("airweave.domains.organizations.subscribers.donke_notification.settings")
    @patch("airweave.domains.organizations.subscribers.donke_notification.httpx.AsyncClient")
    async def test_http_failure_swallowed(self, mock_client_cls, mock_settings):
        """HTTP errors must be logged and swallowed, never crash the event bus."""
        mock_settings.DONKE_URL = "https://donke.example.com"
        mock_settings.DONKE_API_KEY = "key-123"

        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("connection refused")
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        sub = DonkeNotificationSubscriber()
        event = OrganizationLifecycleEvent.created(
            organization_id=ORG_ID, organization_name="X", owner_email="x@x.com",
        )

        # Must not raise
        await sub.handle(event)
