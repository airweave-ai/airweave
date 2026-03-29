"""Tests for _is_retryable predicate in the Mistral OCR client."""

from unittest.mock import MagicMock

import pytest
from httpx import HTTPStatusError, ReadTimeout, Response, TimeoutException

from airweave.domains.ocr.mistral.ocr_client import _is_retryable


def _make_http_error(status_code: int) -> HTTPStatusError:
    """Build a minimal HTTPStatusError with the given status code."""
    response = MagicMock(spec=Response)
    response.status_code = status_code
    return HTTPStatusError(
        message=f"HTTP {status_code}",
        request=MagicMock(),
        response=response,
    )


@pytest.mark.parametrize(
    "status_code, expected",
    [
        (401, False),
        (403, False),
        (404, False),
        (422, False),
        (429, True),
        (500, True),
        (502, True),
        (503, True),
    ],
)
def test_http_status_errors(status_code: int, expected: bool):
    assert _is_retryable(_make_http_error(status_code)) is expected


def test_timeout_is_retryable():
    assert _is_retryable(TimeoutException("timed out")) is True


def test_read_timeout_is_retryable():
    assert _is_retryable(ReadTimeout("read timed out")) is True


def test_generic_exception_is_retryable():
    assert _is_retryable(RuntimeError("something broke")) is True
