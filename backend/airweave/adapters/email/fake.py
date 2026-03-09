"""Fake email service for tests.

Records all calls for assertion. Supports failure injection via
``should_raise`` — set to any exception instance to simulate send failures.
"""

from typing import Optional

from airweave.core.protocols.email import EmailService


class FakeEmailService(EmailService):
    """In-memory fake for EmailService protocol."""

    def __init__(self, *, should_raise: Optional[Exception] = None) -> None:
        """Initialize FakeEmailService."""
        self._calls: list[tuple[str, ...]] = []
        self._should_raise = should_raise

    async def send(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        *,
        from_email: Optional[str] = None,
        scheduled_at: Optional[str] = None,
    ) -> bool:
        """Record call and return True."""
        self._calls.append(("send", to_email, subject))
        if self._should_raise:
            raise self._should_raise
        return True

    async def send_welcome(self, to_email: str, user_name: str) -> None:
        """Record call."""
        self._calls.append(("send_welcome", to_email, user_name))
        if self._should_raise:
            raise self._should_raise

    # --- Assertion helpers ---

    def assert_called(self, method_name: str) -> tuple:
        """Assert a method was called and return the call tuple."""
        for call in self._calls:
            if call[0] == method_name:
                return call
        raise AssertionError(f"{method_name} was not called")

    def assert_not_called(self, method_name: str) -> None:
        """Assert a method was never called."""
        for call in self._calls:
            if call[0] == method_name:
                raise AssertionError(f"{method_name} was called unexpectedly")

    def call_count(self, method_name: str) -> int:
        """Return number of times a method was called."""
        return sum(1 for name, *_ in self._calls if name == method_name)

    def get_calls(self, method_name: str) -> list[tuple]:
        """Return all calls for a method."""
        return [call for call in self._calls if call[0] == method_name]
