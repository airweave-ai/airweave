"""Unit tests for rate limiting exceptions."""

from airweave.domains.sources.rate_limiting.exceptions import InternalRateLimitExceeded


def test_carries_retry_after_and_source():
    exc = InternalRateLimitExceeded(retry_after=5.0, source_short_name="notion")
    assert exc.retry_after == 5.0
    assert exc.source_short_name == "notion"


def test_message_includes_source_and_timing():
    exc = InternalRateLimitExceeded(retry_after=2.5, source_short_name="slack")
    msg = str(exc)
    assert "slack" in msg
    assert "2.5" in msg


def test_is_exception():
    exc = InternalRateLimitExceeded(retry_after=1.0, source_short_name="github")
    assert isinstance(exc, Exception)
