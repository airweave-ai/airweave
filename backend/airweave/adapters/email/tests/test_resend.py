"""Tests for the ResendEmailService adapter.

All Resend I/O is patched — only delegation is verified.
"""

from unittest.mock import AsyncMock, patch

import pytest

from airweave.adapters.email.resend import ResendEmailService
from airweave.core.protocols.email import EmailService


class TestProtocolCompliance:
    def test_is_instance_of_email_service(self):
        assert isinstance(ResendEmailService(), EmailService)


class TestSend:
    @pytest.mark.asyncio
    async def test_delegates_to_send_email_via_resend(self):
        with patch(
            "airweave.adapters.email.resend.send_email_via_resend",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_send:
            svc = ResendEmailService()
            result = await svc.send(
                "user@example.com",
                "Subject",
                "<p>Hello</p>",
                from_email="noreply@example.com",
                scheduled_at="2026-03-06T12:00:00Z",
            )

            assert result is True
            mock_send.assert_awaited_once_with(
                to_email="user@example.com",
                subject="Subject",
                html_body="<p>Hello</p>",
                from_email="noreply@example.com",
                scheduled_at="2026-03-06T12:00:00Z",
            )

    @pytest.mark.asyncio
    async def test_returns_false_on_failure(self):
        with patch(
            "airweave.adapters.email.resend.send_email_via_resend",
            new_callable=AsyncMock,
            return_value=False,
        ):
            svc = ResendEmailService()
            result = await svc.send("user@example.com", "Subject", "<p>Body</p>")
            assert result is False


class TestSendWelcome:
    @pytest.mark.asyncio
    async def test_delegates_to_send_welcome_email(self):
        with patch(
            "airweave.adapters.email.resend.send_welcome_email",
            new_callable=AsyncMock,
        ) as mock_welcome:
            svc = ResendEmailService()
            await svc.send_welcome("user@example.com", "Test User")
            mock_welcome.assert_awaited_once_with("user@example.com", "Test User")
