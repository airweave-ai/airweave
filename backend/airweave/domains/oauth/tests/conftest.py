"""OAuth domain test fixtures.

Provides mock OAuth services and helpers for testing OAuthFlowService
without real OAuth providers or database.
"""

from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Mock OAuth2 service
# ---------------------------------------------------------------------------


class MockOAuth2Service:
    """Mock oauth2_service for testing."""

    def __init__(self) -> None:
        """Initialize with configurable responses."""
        self.auth_url = "https://provider.example.com/authorize?state=test"
        self.code_verifier = "test-code-verifier"
        self.token_response = MagicMock(
            access_token="test-access-token",
            refresh_token="test-refresh-token",
            model_dump=lambda: {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
            },
        )
        self.should_raise_on_exchange: Optional[Exception] = None

    async def generate_auth_url_with_redirect(self, *args, **kwargs):
        """Return canned auth URL and code verifier."""
        return self.auth_url, self.code_verifier

    async def exchange_authorization_code_for_token_with_redirect(self, **kwargs):
        """Return canned token response or raise."""
        if self.should_raise_on_exchange:
            raise self.should_raise_on_exchange
        return self.token_response


# ---------------------------------------------------------------------------
# Mock OAuth1 service
# ---------------------------------------------------------------------------


class MockOAuth1Service:
    """Mock oauth1_service for testing."""

    def __init__(self) -> None:
        """Initialize with configurable responses."""
        self.request_token_response = MagicMock(
            oauth_token="test-request-token",
            oauth_token_secret="test-request-token-secret",
        )
        self.access_token_response = MagicMock(
            oauth_token="test-access-token",
            oauth_token_secret="test-access-token-secret",
        )
        self.should_raise_on_exchange: Optional[Exception] = None

    async def get_request_token(self, **kwargs):
        """Return canned request token."""
        return self.request_token_response

    async def exchange_token(self, **kwargs):
        """Return canned access token or raise."""
        if self.should_raise_on_exchange:
            raise self.should_raise_on_exchange
        return self.access_token_response


# ---------------------------------------------------------------------------
# Mock integration settings
# ---------------------------------------------------------------------------


class MockOAuth2Settings:
    """Fake OAuth2Settings."""

    token_url = "https://provider.example.com/token"
    authorize_url = "https://provider.example.com/authorize"


class MockOAuth1Settings:
    """Fake OAuth1Settings — must pass isinstance check."""

    request_token_url = "https://provider.example.com/request_token"
    authorize_url = "https://provider.example.com/authorize"
    access_token_url = "https://provider.example.com/access_token"
    consumer_key = "platform-consumer-key"
    consumer_secret = "platform-consumer-secret"


class MockIntegrationSettings:
    """Mock integration_settings that returns OAuth2 or OAuth1 settings by short_name."""

    def __init__(self) -> None:
        """Initialize with default OAuth2 settings."""
        self._settings: dict[str, Any] = {}

    def seed_oauth2(self, short_name: str) -> None:
        """Seed OAuth2 settings for a source."""
        self._settings[short_name] = MockOAuth2Settings()

    def seed_oauth1(self, short_name: str) -> None:
        """Seed OAuth1 settings for a source."""
        from airweave.platform.auth.schemas import OAuth1Settings as RealOAuth1Settings

        # Create a real OAuth1Settings-like mock that passes isinstance
        mock = MagicMock(spec=RealOAuth1Settings)
        mock.request_token_url = "https://provider.example.com/request_token"
        mock.authorize_url = "https://provider.example.com/authorize"
        mock.access_token_url = "https://provider.example.com/access_token"
        mock.consumer_key = "platform-consumer-key"
        mock.consumer_secret = "platform-consumer-secret"
        self._settings[short_name] = mock

    async def get_by_short_name(self, short_name: str) -> Optional[Any]:
        """Return configured settings or None."""
        return self._settings.get(short_name)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_oauth2_service():
    """Mock OAuth2 service."""
    return MockOAuth2Service()


@pytest.fixture
def mock_oauth1_service():
    """Mock OAuth1 service."""
    return MockOAuth1Service()


@pytest.fixture
def mock_integration_settings():
    """Mock integration settings."""
    return MockIntegrationSettings()
