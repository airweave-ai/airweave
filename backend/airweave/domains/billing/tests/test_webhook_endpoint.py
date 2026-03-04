"""Unit tests for the Stripe webhook endpoint error handling."""

from unittest.mock import AsyncMock

import pytest

from airweave.api.v1.endpoints.billing import stripe_webhook


class TestStripeWebhookEndpoint:
    @pytest.mark.asyncio
    async def test_value_error_returns_400(self, db):
        """ValueError from process_webhook returns 400."""
        request = AsyncMock()
        request.body = AsyncMock(return_value=b"payload")
        webhook = AsyncMock()
        webhook.process_webhook = AsyncMock(side_effect=ValueError("bad signature"))

        response = await stripe_webhook(
            request=request,
            stripe_signature="sig_test",
            db=db,
            webhook=webhook,
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_unexpected_error_returns_500(self, db):
        """Unexpected exception from process_webhook returns 500."""
        request = AsyncMock()
        request.body = AsyncMock(return_value=b"payload")
        webhook = AsyncMock()
        webhook.process_webhook = AsyncMock(side_effect=RuntimeError("boom"))

        response = await stripe_webhook(
            request=request,
            stripe_signature="sig_test",
            db=db,
            webhook=webhook,
        )

        assert response.status_code == 500
