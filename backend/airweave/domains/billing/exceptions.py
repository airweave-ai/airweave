"""Billing domain exceptions."""

import functools

from airweave.core.exceptions import ExternalServiceError, InvalidStateError, NotFoundException


class BillingNotFoundError(NotFoundException):
    """Raised when a billing record or subscription is not found."""

    def __init__(self, message: str = "Billing record not found"):
        """Initialize with default message."""
        super().__init__(message)


class BillingStateError(InvalidStateError):
    """Raised when a billing operation is invalid for the current state."""

    def __init__(self, message: str = "Invalid billing state"):
        """Initialize with default message."""
        super().__init__(message)


class BillingNotAvailableError(InvalidStateError):
    """Raised by NullPaymentGateway when billing is not enabled."""

    def __init__(self, message: str = "Billing is not enabled for this instance"):
        """Initialize with default message."""
        super().__init__(message)


class PaymentGatewayError(ExternalServiceError):
    """Wraps ExternalServiceError from the payment adapter at the domain boundary."""

    def __init__(self, message: str = "Payment gateway error"):
        """Initialize with default message."""
        super().__init__(service_name="PaymentGateway", message=message)


def wrap_gateway_errors(fn):
    """Decorator: catch ExternalServiceError from payment gateway, wrap as PaymentGatewayError."""

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except ExternalServiceError as e:
            raise PaymentGatewayError(message=e.message) from e

    return wrapper
