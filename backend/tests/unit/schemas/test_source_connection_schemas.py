"""Unit tests for source connection Pydantic schemas."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from airweave.schemas.source_connection import OAuthTokenAuthentication


class TestOAuthTokenAuthenticationExpiresIn:
    """Tests for expires_in → expires_at conversion on OAuthTokenAuthentication."""

    def test_expires_in_converted_to_expires_at(self):
        auth = OAuthTokenAuthentication(
            access_token="tok",
            expires_in=3600,
        )
        assert auth.expires_at is not None
        expected = datetime.now(timezone.utc) + timedelta(seconds=3600)
        delta = abs((auth.expires_at - expected).total_seconds())
        assert delta < 2, f"expires_at off by {delta}s"

    def test_expires_at_takes_precedence_over_expires_in(self):
        explicit_expiry = datetime.now(timezone.utc) + timedelta(hours=2)
        auth = OAuthTokenAuthentication(
            access_token="tok",
            expires_at=explicit_expiry,
            expires_in=60,
        )
        # expires_at must not be overwritten by expires_in
        assert auth.expires_at == explicit_expiry

    def test_neither_expires_field_is_valid(self):
        auth = OAuthTokenAuthentication(access_token="tok")
        assert auth.expires_at is None
        assert auth.expires_in is None

    def test_expired_expires_in_raises(self):
        with pytest.raises(ValidationError, match="Token has already expired"):
            OAuthTokenAuthentication(
                access_token="tok",
                expires_in=-1,
            )

    def test_expires_at_backward_compatibility(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        auth = OAuthTokenAuthentication(access_token="tok", expires_at=future)
        assert auth.expires_at == future
        assert auth.expires_in is None

    def test_blank_access_token_still_rejected(self):
        with pytest.raises(ValidationError, match="access_token cannot be empty"):
            OAuthTokenAuthentication(access_token="   ", expires_in=3600)
