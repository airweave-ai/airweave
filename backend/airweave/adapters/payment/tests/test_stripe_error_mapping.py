"""Tests for StripePaymentGateway._map_stripe_error.

Verifies each Stripe exception type routes to the correct protocol exception.
Uses table-driven cases so adding a new Stripe error type is trivial.
"""

from dataclasses import dataclass
from typing import Type

import pytest
from stripe.error import (  # type: ignore[attr-defined]
    APIConnectionError,
    InvalidRequestError,
    RateLimitError,
    StripeError,
)

from airweave.adapters.payment.stripe import StripePaymentGateway
from airweave.core.protocols.payment import (
    PaymentProviderError,
    PaymentProviderInvalidRequestError,
    PaymentProviderRateLimitError,
    PaymentProviderUnavailableError,
)


@dataclass
class ErrorMappingCase:
    name: str
    stripe_error: StripeError
    expected_type: Type[PaymentProviderError]


def _make_rate_limit_error():
    return RateLimitError("Too many requests")


def _make_api_connection_error():
    return APIConnectionError("Connection refused")


def _make_invalid_request_error():
    return InvalidRequestError("No such customer", param="customer_id")


def _make_generic_stripe_error():
    return StripeError("Something went wrong")


ERROR_MAPPING_CASES = [
    ErrorMappingCase(
        name="rate_limit",
        stripe_error=_make_rate_limit_error(),
        expected_type=PaymentProviderRateLimitError,
    ),
    ErrorMappingCase(
        name="api_connection",
        stripe_error=_make_api_connection_error(),
        expected_type=PaymentProviderUnavailableError,
    ),
    ErrorMappingCase(
        name="invalid_request",
        stripe_error=_make_invalid_request_error(),
        expected_type=PaymentProviderInvalidRequestError,
    ),
    ErrorMappingCase(
        name="generic_stripe_error",
        stripe_error=_make_generic_stripe_error(),
        expected_type=PaymentProviderError,
    ),
]


@pytest.mark.parametrize("case", ERROR_MAPPING_CASES, ids=lambda c: c.name)
class TestMapStripeError:
    def test_returns_correct_type(self, case: ErrorMappingCase):
        result = StripePaymentGateway._map_stripe_error(case.stripe_error, "test_op")
        assert isinstance(result, case.expected_type)

    def test_message_contains_operation(self, case: ErrorMappingCase):
        result = StripePaymentGateway._map_stripe_error(case.stripe_error, "create_customer")
        assert "create_customer" in result.message

    def test_message_contains_original_error(self, case: ErrorMappingCase):
        result = StripePaymentGateway._map_stripe_error(case.stripe_error, "op")
        assert str(case.stripe_error) in result.message

    def test_all_results_are_payment_provider_error(self, case: ErrorMappingCase):
        result = StripePaymentGateway._map_stripe_error(case.stripe_error, "op")
        assert isinstance(result, PaymentProviderError)
