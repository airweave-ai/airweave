"""Unit tests for rate limiting types."""

import pytest

from airweave.domains.sources.rate_limiting.types import RateLimitConfig


def test_frozen_dataclass():
    cfg = RateLimitConfig(limit=100, window_seconds=60)
    assert cfg.limit == 100
    assert cfg.window_seconds == 60

    with pytest.raises(AttributeError):
        cfg.limit = 200


def test_equality():
    a = RateLimitConfig(limit=100, window_seconds=60)
    b = RateLimitConfig(limit=100, window_seconds=60)
    assert a == b


def test_inequality():
    a = RateLimitConfig(limit=100, window_seconds=60)
    b = RateLimitConfig(limit=200, window_seconds=60)
    assert a != b
