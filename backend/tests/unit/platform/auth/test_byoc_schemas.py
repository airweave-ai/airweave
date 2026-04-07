"""Unit tests for BYOC-related changes to OAuth schemas.

Verifies that OAuth2Settings and OAuth1Settings accept optional
client_id / consumer_key (needed when the YAML entry exists purely
so BYOC callers can override with their own credentials).
"""

import pytest
from pydantic import ValidationError

from airweave.platform.auth.schemas import OAuth1Settings, OAuth2Settings


# ---------------------------------------------------------------------------
# OAuth2Settings – optional client_id / client_secret
# ---------------------------------------------------------------------------


class TestOAuth2SettingsOptionalCredentials:
    """client_id and client_secret should be Optional[str] = None."""

    _BASE = dict(
        integration_short_name="test_source",
        url="https://provider.com/authorize",
        backend_url="https://provider.com/token",
        grant_type="authorization_code",
        content_type="application/x-www-form-urlencoded",
        client_credential_location="body",
    )

    def test_both_credentials_present(self):
        s = OAuth2Settings(
            **self._BASE, client_id="cid", client_secret="csec"
        )
        assert s.client_id == "cid"
        assert s.client_secret == "csec"

    def test_client_id_none(self):
        s = OAuth2Settings(**self._BASE, client_id=None, client_secret="csec")
        assert s.client_id is None

    def test_client_secret_none(self):
        s = OAuth2Settings(**self._BASE, client_id="cid", client_secret=None)
        assert s.client_secret is None

    def test_both_credentials_none(self):
        s = OAuth2Settings(**self._BASE)
        assert s.client_id is None
        assert s.client_secret is None

    def test_url_still_required(self):
        with pytest.raises(ValidationError):
            OAuth2Settings(
                integration_short_name="x",
                url="",
                backend_url="https://provider.com/token",
                grant_type="authorization_code",
                content_type="application/x-www-form-urlencoded",
                client_credential_location="body",
            )

    def test_backend_url_still_required(self):
        with pytest.raises(ValidationError):
            OAuth2Settings(
                integration_short_name="x",
                url="https://provider.com/authorize",
                backend_url="",
                grant_type="authorization_code",
                content_type="application/x-www-form-urlencoded",
                client_credential_location="body",
            )


# ---------------------------------------------------------------------------
# OAuth1Settings – optional consumer_key / consumer_secret
# ---------------------------------------------------------------------------


class TestOAuth1SettingsOptionalCredentials:
    """consumer_key and consumer_secret should be Optional[str] = None."""

    _BASE = dict(
        integration_short_name="test_oauth1",
        request_token_url="https://provider.com/request_token",
        authorization_url="https://provider.com/authorize",
        access_token_url="https://provider.com/access_token",
    )

    def test_both_credentials_present(self):
        s = OAuth1Settings(
            **self._BASE, consumer_key="ck", consumer_secret="cs"
        )
        assert s.consumer_key == "ck"
        assert s.consumer_secret == "cs"

    def test_consumer_key_none(self):
        s = OAuth1Settings(**self._BASE, consumer_key=None, consumer_secret="cs")
        assert s.consumer_key is None

    def test_consumer_secret_none(self):
        s = OAuth1Settings(**self._BASE, consumer_key="ck", consumer_secret=None)
        assert s.consumer_secret is None

    def test_both_credentials_none(self):
        s = OAuth1Settings(**self._BASE)
        assert s.consumer_key is None
        assert s.consumer_secret is None

    def test_request_token_url_still_required(self):
        with pytest.raises(ValidationError):
            OAuth1Settings(
                integration_short_name="x",
                request_token_url="",
                authorization_url="https://p.com/auth",
                access_token_url="https://p.com/access",
            )

    def test_authorization_url_still_required(self):
        with pytest.raises(ValidationError):
            OAuth1Settings(
                integration_short_name="x",
                request_token_url="https://p.com/req",
                authorization_url="",
                access_token_url="https://p.com/access",
            )

    def test_access_token_url_still_required(self):
        with pytest.raises(ValidationError):
            OAuth1Settings(
                integration_short_name="x",
                request_token_url="https://p.com/req",
                authorization_url="https://p.com/auth",
                access_token_url="",
            )
