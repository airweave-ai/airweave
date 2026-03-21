"""Tests for credential validation → HTTP exception translation."""

from airweave.domains.sources.exceptions import (
    SourceAuthError,
    SourceCreationError,
    SourceNotFoundError,
    SourceRateLimitError,
    SourceServerError,
    SourceValidationError,
    SourceError,
)
from airweave.domains.sources.http_translation import http_exception_for_credential_validation
from airweave.domains.sources.token_providers.protocol import AuthProviderKind


def test_source_not_found_maps_to_404():
    exc = SourceNotFoundError("missing")
    http_exc = http_exception_for_credential_validation(exc, source_short_name="missing")
    assert http_exc.status_code == 404
    assert "missing" in http_exc.detail


def test_validation_error_uses_exception_string():
    exc = SourceValidationError("notion", "bad config")
    http_exc = http_exception_for_credential_validation(exc, source_short_name="notion")
    assert http_exc.status_code == 400
    assert "bad config" in http_exc.detail


def test_creation_error_uses_exception_string():
    exc = SourceCreationError("github", "missing field")
    http_exc = http_exception_for_credential_validation(exc, source_short_name="github")
    assert http_exc.status_code == 400
    assert "missing field" in http_exc.detail


def test_auth_error_sanitized_no_raw_upstream_message():
    exc = SourceAuthError(
        "Unauthorized (401) — credentials invalid or revoked. raw body here",
        source_short_name="notion",
        status_code=401,
        token_provider_kind=AuthProviderKind.STATIC,
    )
    http_exc = http_exception_for_credential_validation(exc, source_short_name="notion")
    assert http_exc.status_code == 400
    assert "raw body" not in (http_exc.detail or "").lower()
    assert "Unauthorized (401)" not in (http_exc.detail or "")
    assert "invalid" in http_exc.detail.lower()
    assert "notion" in http_exc.detail.lower()


def test_rate_limit_maps_to_429_with_retry_after():
    exc = SourceRateLimitError(retry_after=42.7, source_short_name="slack")
    http_exc = http_exception_for_credential_validation(exc, source_short_name="slack")
    assert http_exc.status_code == 429
    assert http_exc.headers and http_exc.headers.get("Retry-After") == "42"


def test_server_error_maps_to_502():
    exc = SourceServerError("boom", source_short_name="x", status_code=503)
    http_exc = http_exception_for_credential_validation(exc, source_short_name="notion")
    assert http_exc.status_code == 502
    assert "notion" in http_exc.detail.lower()


def test_generic_source_error_maps_to_400():
    exc = SourceError("Something went wrong", source_short_name="z")
    http_exc = http_exception_for_credential_validation(exc, source_short_name="z")
    assert http_exc.status_code == 400
    assert "Something went wrong" in http_exc.detail


def test_unknown_exception_returns_500():
    http_exc = http_exception_for_credential_validation(
        ValueError("nope"), source_short_name="any"
    )
    assert http_exc.status_code == 500
