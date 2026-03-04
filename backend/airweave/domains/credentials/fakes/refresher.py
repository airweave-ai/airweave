"""Fake implementations for credential refresh protocols."""

from typing import Optional

from airweave.core.exceptions import TokenRefreshError


class FakeCredentialRefresher:
    """Records calls and returns a configurable token."""

    def __init__(
        self,
        *,
        token: str = "fake-refreshed-token",
        fail: bool = False,
    ) -> None:
        self._token = token
        self._fail = fail
        self.call_count = 0

    async def refresh(self) -> str:
        self.call_count += 1
        if self._fail:
            raise TokenRefreshError("fake refresh failure")
        return self._token


class FakeTokenRefresher:
    """Records calls, returns a configurable token. No real timer/lock."""

    def __init__(
        self,
        *,
        token: str = "fake-valid-token",
        fail_on_unauthorized: bool = False,
    ) -> None:
        self._token = token
        self._fail_on_unauthorized = fail_on_unauthorized
        self.get_valid_token_calls: int = 0
        self.refresh_on_unauthorized_calls: int = 0

    async def get_valid_token(self) -> str:
        self.get_valid_token_calls += 1
        return self._token

    async def refresh_on_unauthorized(self) -> str:
        self.refresh_on_unauthorized_calls += 1
        if self._fail_on_unauthorized:
            raise TokenRefreshError("fake: refresh not supported")
        return self._token

    def set_token(self, token: str) -> None:
        self._token = token
