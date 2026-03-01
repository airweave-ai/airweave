"""Tests for identity and payment protocol exception hierarchies.

Verifies:
- Inheritance chains are correct (catch-base-catches-all)
- Attributes (message, retry_after) are set
- str() returns the message
- runtime_checkable protocols accept adapters
"""

from dataclasses import dataclass
from typing import Type

import pytest

from airweave.core.protocols.identity import (
    IdentityProvider,
    IdentityProviderConflictError,
    IdentityProviderError,
    IdentityProviderNotFoundError,
    IdentityProviderRateLimitError,
    IdentityProviderUnavailableError,
)
from airweave.core.protocols.payment import (
    PaymentGatewayProtocol,
    PaymentProviderError,
    PaymentProviderInvalidRequestError,
    PaymentProviderNotFoundError,
    PaymentProviderRateLimitError,
    PaymentProviderUnavailableError,
)


# ---------------------------------------------------------------------------
# Identity exception hierarchy
# ---------------------------------------------------------------------------


@dataclass
class ExceptionCase:
    name: str
    cls: Type[Exception]
    base: Type[Exception]
    message: str = "test error"
    extra_attr: str = ""
    extra_value: object = None


IDENTITY_CASES = [
    ExceptionCase(
        name="base",
        cls=IdentityProviderError,
        base=Exception,
    ),
    ExceptionCase(
        name="rate_limit",
        cls=IdentityProviderRateLimitError,
        base=IdentityProviderError,
        extra_attr="retry_after",
    ),
    ExceptionCase(
        name="unavailable",
        cls=IdentityProviderUnavailableError,
        base=IdentityProviderError,
    ),
    ExceptionCase(
        name="conflict",
        cls=IdentityProviderConflictError,
        base=IdentityProviderError,
    ),
    ExceptionCase(
        name="not_found",
        cls=IdentityProviderNotFoundError,
        base=IdentityProviderError,
    ),
]


@pytest.mark.parametrize("case", IDENTITY_CASES, ids=lambda c: c.name)
class TestIdentityExceptions:
    def test_inherits_from_base(self, case: ExceptionCase):
        assert issubclass(case.cls, case.base)

    def test_message_attribute(self, case: ExceptionCase):
        exc = case.cls(case.message)
        assert exc.message == case.message

    def test_str_contains_message(self, case: ExceptionCase):
        exc = case.cls(case.message)
        assert case.message in str(exc)

    def test_caught_by_base_except(self, case: ExceptionCase):
        with pytest.raises(case.base):
            raise case.cls(case.message)


class TestIdentityRateLimitRetryAfter:
    def test_retry_after_set(self):
        exc = IdentityProviderRateLimitError("slow down", retry_after=60)
        assert exc.retry_after == 60

    def test_retry_after_defaults_to_none(self):
        exc = IdentityProviderRateLimitError("slow down")
        assert exc.retry_after is None


# ---------------------------------------------------------------------------
# Payment exception hierarchy
# ---------------------------------------------------------------------------


PAYMENT_CASES = [
    ExceptionCase(name="base", cls=PaymentProviderError, base=Exception),
    ExceptionCase(name="rate_limit", cls=PaymentProviderRateLimitError, base=PaymentProviderError),
    ExceptionCase(name="unavailable", cls=PaymentProviderUnavailableError, base=PaymentProviderError),
    ExceptionCase(name="not_found", cls=PaymentProviderNotFoundError, base=PaymentProviderError),
    ExceptionCase(name="invalid_request", cls=PaymentProviderInvalidRequestError, base=PaymentProviderError),
]


@pytest.mark.parametrize("case", PAYMENT_CASES, ids=lambda c: c.name)
class TestPaymentExceptions:
    def test_inherits_from_base(self, case: ExceptionCase):
        assert issubclass(case.cls, case.base)

    def test_message_attribute(self, case: ExceptionCase):
        exc = case.cls(case.message)
        assert exc.message == case.message

    def test_str_contains_message(self, case: ExceptionCase):
        exc = case.cls(case.message)
        assert case.message in str(exc)

    def test_caught_by_base_except(self, case: ExceptionCase):
        with pytest.raises(case.base):
            raise case.cls(case.message)


# ---------------------------------------------------------------------------
# runtime_checkable smoke tests
# ---------------------------------------------------------------------------


class TestRuntimeCheckable:
    def test_null_identity_is_identity_provider(self):
        from airweave.adapters.identity.null import NullIdentityProvider

        assert isinstance(NullIdentityProvider(), IdentityProvider)

    def test_fake_identity_is_identity_provider(self):
        from airweave.adapters.identity.fake import FakeIdentityProvider

        assert isinstance(FakeIdentityProvider(), IdentityProvider)
