"""Billing domain exceptions."""

import functools

from airweave.core.exceptions import InvalidStateError, NotFoundException
from airweave.core.protocols.payment import PaymentProviderError


class BillingNotFoundError(NotFoundException):
    """Raised when a billing record or subscription is not found."""

    def __init__(self, message: str = "Billing record not found"):
        """Initialize BillingNotFoundError."""
        super().__init__(message)


class BillingStateError(InvalidStateError):
    """Raised when a billing operation is invalid for the current state."""

    def __init__(self, message: str = "Invalid billing state"):
        """Initialize BillingStateError."""
        super().__init__(message)


class BillingNotAvailableError(InvalidStateError):
    """Raised by NullPaymentGateway when billing is not enabled."""

    def __init__(self, message: str = "Billing is not enabled for this instance"):
        """Initialize BillingNotAvailableError."""
        super().__init__(message)


class PaymentGatewayError(PaymentProviderError):
    """Domain-level wrapper for payment provider failures.

    Inherits from ``PaymentProviderError`` so callers can catch either the
    protocol base or this domain-specific subclass.
    """

    def __init__(self, message: str = "Payment gateway error"):
        """Initialize PaymentGatewayError."""
        super().__init__(message)


def wrap_gateway_errors(fn):
    """Decorator: catch PaymentProviderError from payment gateway, wrap as PaymentGatewayError."""

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except PaymentProviderError as e:
            raise PaymentGatewayError(message=e.message) from e

    return wrapper
