"""Fake OAuth flow service for testing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from airweave.domains.oauth.types import OAuthCompletionResult, OAuthInitResult


class FakeOAuthFlowService:
    """Test implementation of OAuthFlowServiceProtocol.

    Returns canned results by default. Set should_raise for error paths.

    Usage:
        fake = FakeOAuthFlowService()
        result = await fake.initiate_oauth2(...)
        assert result.auth_url == "https://fake-auth.example.com"

        # Error path:
        fake.set_should_raise(OAuthSessionNotFoundError())
    """

    def __init__(self, should_raise: Optional[Exception] = None) -> None:
        """Initialize with optional error injection."""
        self._should_raise = should_raise
        self.initiated_flows: list[dict] = []
        self.completed_flows: list[dict] = []

    def _maybe_raise(self) -> None:
        if self._should_raise is not None:
            raise self._should_raise

    async def initiate_oauth2(
        self,
        short_name: str,
        payload: dict,
        organization_id: Any,
        redirect_url: Optional[str],
        byoc_client_id: Optional[str],
        byoc_client_secret: Optional[str],
        template_configs: Optional[dict],
        db: Any,
        uow: Any,
    ) -> OAuthInitResult:
        """Return canned OAuthInitResult."""
        self._maybe_raise()
        result = OAuthInitResult(
            auth_url="https://fake-oauth2-provider.example.com/authorize",
            proxy_url="https://api.test/source-connections/authorize/abc12345",
            proxy_expiry=datetime.now(timezone.utc) + timedelta(hours=24),
            init_session_id=uuid4(),
            redirect_session_id=uuid4(),
        )
        self.initiated_flows.append(
            {
                "type": "oauth2",
                "short_name": short_name,
                "result": result,
            }
        )
        return result

    async def initiate_oauth1(
        self,
        short_name: str,
        payload: dict,
        organization_id: Any,
        redirect_url: Optional[str],
        byoc_consumer_key: Optional[str],
        byoc_consumer_secret: Optional[str],
        db: Any,
        uow: Any,
    ) -> OAuthInitResult:
        """Return canned OAuthInitResult for OAuth1."""
        self._maybe_raise()
        result = OAuthInitResult(
            auth_url="https://fake-oauth1-provider.example.com/authorize",
            proxy_url="https://api.test/source-connections/authorize/xyz98765",
            proxy_expiry=datetime.now(timezone.utc) + timedelta(hours=24),
            init_session_id=uuid4(),
            redirect_session_id=uuid4(),
        )
        self.initiated_flows.append(
            {
                "type": "oauth1",
                "short_name": short_name,
                "result": result,
            }
        )
        return result

    async def complete_oauth2_callback(
        self,
        state: str,
        code: str,
        db: Any,
    ) -> OAuthCompletionResult:
        """Return canned OAuthCompletionResult."""
        self._maybe_raise()
        result = OAuthCompletionResult(
            token_response=type(
                "FakeTokenResponse",
                (),
                {
                    "access_token": "fake-access-token",
                    "refresh_token": "fake-refresh-token",
                    "model_dump": lambda self: {
                        "access_token": self.access_token,
                        "refresh_token": self.refresh_token,
                    },
                },
            )(),
            init_session=type(
                "FakeInitSession",
                (),
                {
                    "id": uuid4(),
                    "short_name": "fake_source",
                    "payload": {},
                    "overrides": {},
                },
            )(),
            original_payload={},
            overrides={},
            short_name="fake_source",
            organization_id=uuid4(),
        )
        self.completed_flows.append(
            {
                "type": "oauth2",
                "state": state,
                "result": result,
            }
        )
        return result

    async def complete_oauth1_callback(
        self,
        oauth_token: str,
        oauth_verifier: str,
        db: Any,
    ) -> OAuthCompletionResult:
        """Return canned OAuthCompletionResult for OAuth1."""
        self._maybe_raise()
        result = OAuthCompletionResult(
            token_response=type(
                "FakeOAuth1TokenResponse",
                (),
                {
                    "oauth_token": "fake-oauth-token",
                    "oauth_token_secret": "fake-oauth-token-secret",
                },
            )(),
            init_session=type(
                "FakeInitSession",
                (),
                {
                    "id": uuid4(),
                    "short_name": "fake_source",
                    "payload": {},
                    "overrides": {},
                },
            )(),
            original_payload={},
            overrides={},
            short_name="fake_source",
            organization_id=uuid4(),
        )
        self.completed_flows.append(
            {
                "type": "oauth1",
                "oauth_token": oauth_token,
                "result": result,
            }
        )
        return result

    # Test helpers

    def set_should_raise(self, exc: Optional[Exception]) -> None:
        """Configure the exception to raise on next call."""
        self._should_raise = exc

    def clear(self) -> None:
        """Reset all state."""
        self._should_raise = None
        self.initiated_flows.clear()
        self.completed_flows.clear()
