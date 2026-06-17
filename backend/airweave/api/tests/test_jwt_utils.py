"""Tests for JWT claim extraction helpers."""

from unittest.mock import MagicMock, patch

from jose import jwt as jose_jwt

from airweave.api.jwt_utils import extract_claims, extract_sid


def _make_request(authorization: str = "") -> MagicMock:
    request = MagicMock()
    request.headers = {"authorization": authorization} if authorization else {}
    return request


def _encode_claims(claims: dict) -> str:
    """Create an unsigned JWT with the given claims (for testing only)."""
    return jose_jwt.encode(claims, "secret", algorithm="HS256")


class TestExtractClaims:
    def test_valid_bearer_token(self):
        token = _encode_claims({"sub": "user-1", "iat": 1000})
        request = _make_request(f"Bearer {token}")
        claims = extract_claims(request)
        assert claims is not None
        assert claims["sub"] == "user-1"
        assert claims["iat"] == 1000

    def test_missing_authorization_header(self):
        request = MagicMock()
        request.headers = {}
        assert extract_claims(request) is None

    def test_empty_authorization_header(self):
        request = _make_request("")
        assert extract_claims(request) is None

    def test_non_bearer_scheme(self):
        request = _make_request("Basic dXNlcjpwYXNz")
        assert extract_claims(request) is None

    def test_malformed_jwt(self):
        request = _make_request("Bearer not.a.valid.jwt.at.all")
        assert extract_claims(request) is None

    def test_empty_bearer_value(self):
        request = _make_request("Bearer ")
        assert extract_claims(request) is None


class TestExtractSid:
    def test_returns_sid_when_present(self):
        token = _encode_claims({"https://airweave.ai/sid": "sess-abc"})
        request = _make_request(f"Bearer {token}")
        with patch("airweave.api.jwt_utils.settings") as mock_settings:
            mock_settings.AUTH0_SID_CLAIM_KEY = "https://airweave.ai/sid"
            assert extract_sid(request) == "sess-abc"

    def test_returns_none_when_no_sid_claim(self):
        token = _encode_claims({"sub": "user-1"})
        request = _make_request(f"Bearer {token}")
        with patch("airweave.api.jwt_utils.settings") as mock_settings:
            mock_settings.AUTH0_SID_CLAIM_KEY = "https://airweave.ai/sid"
            assert extract_sid(request) is None

    def test_returns_none_when_no_token(self):
        request = _make_request("")
        assert extract_sid(request) is None
