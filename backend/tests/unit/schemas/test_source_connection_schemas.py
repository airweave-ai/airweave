"""Unit tests for source connection schemas."""

from datetime import datetime, timedelta, timezone

from airweave.schemas.source_connection import OAuthTokenAuthentication


def test_oauth_token_authentication_accepts_expired_tokens_for_stored_credentials():
    """Expired stored OAuth tokens must deserialize so refresh logic can run."""
    expired = datetime.now(timezone.utc) - timedelta(minutes=10)

    auth = OAuthTokenAuthentication(
        access_token="stored-access-token",
        refresh_token="stored-refresh-token",
        expires_at=expired,
    )

    assert auth.expires_at == expired
    assert auth.refresh_token == "stored-refresh-token"
