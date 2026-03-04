"""Usage domain exceptions."""

from typing import Optional

from airweave.core.exceptions import InvalidStateError


class UsageLimitExceededError(InvalidStateError):
    """Raised when an action would exceed the organization's usage limit."""

    def __init__(
        self,
        action_type: str,
        limit: int,
        current_usage: int,
        message: Optional[str] = None,
    ) -> None:
        """Initialize with action type, limit, and current usage."""
        if message is None:
            message = f"Usage limit exceeded for {action_type}: {current_usage}/{limit}"
        self.action_type = action_type
        self.limit = limit
        self.current_usage = current_usage
        super().__init__(message)


class PaymentRequiredError(InvalidStateError):
    """Raised when an action is blocked due to billing/payment status."""

    def __init__(
        self,
        action_type: str,
        payment_status: str,
        message: Optional[str] = None,
    ) -> None:
        """Initialize with action type and payment status."""
        if message is None:
            message = (
                f"Action '{action_type}' is not allowed due to payment status: {payment_status}"
            )
        self.action_type = action_type
        self.payment_status = payment_status
        super().__init__(message)
