"""Unit tests for the Stripe webhook endpoint error handling."""

from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import MultipleResultsFound

from airweave.api.v1.endpoints.billing import stripe_webhook
from airweave.core.exceptions import PermissionException
from airweave.domains.billing.exceptions import (
    BillingNotAvailableError,
    BillingNotFoundError,
    BillingStateError,
    PaymentGatewayError,
)


def _make_validation_error():
    """Create a real Pydantic ValidationError instance."""
    from pydantic import BaseModel

    class _M(BaseModel):
        x: int

    try:
        _M(x="bad")
    except ValidationError as e:
        return e

    pytest.fail("Expected ValidationError was not raised")
    return None


class TestStripeWebhookEndpoint:
    @pytest.mark.asyncio
    async def test_success_returns_200(self, db):
        """Successful process_webhook returns 200."""
        request = AsyncMock()
        request.body = AsyncMock(return_value=b"payload")
        webhook = AsyncMock()
        webhook.process_webhook = AsyncMock(return_value=None)

        response = await stripe_webhook(
            request=request,
            stripe_signature="sig_test",
            db=db,
            webhook=webhook,
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_missing_signature_returns_400(self, db):
        """Missing Stripe-Signature header returns 400."""
        request = AsyncMock()
        request.body = AsyncMock(return_value=b"payload")
        webhook = AsyncMock()

        response = await stripe_webhook(
            request=request,
            stripe_signature=None,
            db=db,
            webhook=webhook,
        )

        assert response.status_code == 400
        webhook.process_webhook.assert_not_called()

    @pytest.mark.asyncio
    async def test_body_read_failure_returns_400(self, db):
        """Exception reading request body returns 400."""
        request = AsyncMock()
        request.body = AsyncMock(side_effect=Exception("disconnect"))
        webhook = AsyncMock()

        response = await stripe_webhook(
            request=request,
            stripe_signature="sig_test",
            db=db,
            webhook=webhook,
        )

        assert response.status_code == 400
        webhook.process_webhook.assert_not_called()

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
    async def test_validation_error_returns_400(self, db):
        """Pydantic ValidationError is a ValueError subclass, caught as 400."""
        request = AsyncMock()
        request.body = AsyncMock(return_value=b"payload")
        webhook = AsyncMock()
        webhook.process_webhook = AsyncMock(side_effect=_make_validation_error())

        response = await stripe_webhook(
            request=request,
            stripe_signature="sig_test",
            db=db,
            webhook=webhook,
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exc",
        [
            MultipleResultsFound(),
            PermissionException("forbidden"),
            BillingNotFoundError("not found"),
            BillingStateError("bad state"),
            BillingNotAvailableError("unavailable"),
        ],
        ids=lambda e: type(e).__name__,
    )
    async def test_non_retryable_error_returns_200(self, db, exc):
        """Non-retryable exceptions return 200 so Stripe won't retry."""
        request = AsyncMock()
        request.body = AsyncMock(return_value=b"payload")
        webhook = AsyncMock()
        webhook.process_webhook = AsyncMock(side_effect=exc)

        response = await stripe_webhook(
            request=request,
            stripe_signature="sig_test",
            db=db,
            webhook=webhook,
        )

        assert response.status_code == 200

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

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exc",
        [
            PaymentGatewayError("stripe down"),
            KeyError("missing"),
            AttributeError("no attr"),
            TypeError("wrong type"),
        ],
        ids=lambda e: type(e).__name__,
    )
    async def test_retryable_error_returns_500(self, db, exc):
        """Retryable exceptions return 500 so Stripe retries later."""
        request = AsyncMock()
        request.body = AsyncMock(return_value=b"payload")
        webhook = AsyncMock()
        webhook.process_webhook = AsyncMock(side_effect=exc)

        response = await stripe_webhook(
            request=request,
            stripe_signature="sig_test",
            db=db,
            webhook=webhook,
        )

        assert response.status_code == 500
