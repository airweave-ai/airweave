"""Tests for auth provider exception __init__ bodies."""

from airweave.domains.auth_provider.exceptions import (
    AuthProviderAccountNotFoundError,
    AuthProviderError,
    AuthProviderMissingFieldsError,
    AuthProviderRateLimitError,
    AuthProviderServerError,
    AuthProviderTemporaryError,
)


def test_base_error_stores_provider_name():
    err = AuthProviderError("boom", provider_name="pipedream")
    assert err.provider_name == "pipedream"
    assert str(err) == "boom"


def test_account_not_found_stores_account_id():
    err = AuthProviderAccountNotFoundError(
        "gone", provider_name="composio", account_id="acc-123"
    )
    assert err.account_id == "acc-123"
    assert err.provider_name == "composio"


def test_missing_fields_stores_fields():
    err = AuthProviderMissingFieldsError(
        "missing",
        provider_name="pipedream",
        missing_fields=["api_key"],
        available_fields=["access_token", "refresh_token"],
    )
    assert err.missing_fields == ["api_key"]
    assert err.available_fields == ["access_token", "refresh_token"]


def test_missing_fields_defaults_to_empty():
    err = AuthProviderMissingFieldsError("missing")
    assert err.missing_fields == []
    assert err.available_fields == []


def test_rate_limit_stores_retry_after():
    err = AuthProviderRateLimitError("slow down", provider_name="composio", retry_after=60.0)
    assert err.retry_after == 60.0


def test_server_error_stores_status_code():
    err = AuthProviderServerError("oops", provider_name="pipedream", status_code=502)
    assert err.status_code == 502


def test_temporary_error_is_server_error_alias():
    assert AuthProviderTemporaryError is AuthProviderServerError
