"""Tests for the NullEmailService adapter.

Verifies that the no-op adapter satisfies the EmailService protocol
and performs no side-effects.
"""

import pytest

from airweave.adapters.email.null import NullEmailService
from airweave.core.protocols.email import EmailService


class TestProtocolCompliance:
    def test_is_instance_of_email_service(self):
        assert isinstance(NullEmailService(), EmailService)


class TestSend:
    @pytest.mark.asyncio
    async def test_returns_false(self):
        svc = NullEmailService()
        result = await svc.send("user@example.com", "Subject", "<p>Hello</p>")
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_with_optional_params(self):
        svc = NullEmailService()
        result = await svc.send(
            "user@example.com",
            "Subject",
            "<p>Hello</p>",
            from_email="noreply@example.com",
            scheduled_at="2026-03-06T12:00:00Z",
        )
        assert result is False


class TestSendWelcome:
    @pytest.mark.asyncio
    async def test_does_not_raise(self):
        svc = NullEmailService()
        await svc.send_welcome("user@example.com", "Test User")
