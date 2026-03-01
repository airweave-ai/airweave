"""Tests for the protocol injection utility (api/inject.py).

Verifies:
- _resolve_field_name maps protocol types to Container field names
- Unknown protocol types raise TypeError with available fields
- Cache is populated on first call and reused
"""

import pytest

from airweave.api.inject import _INJECT_CACHE, _resolve_field_name
from airweave.core.container.container import Container
from airweave.core.protocols.event_bus import EventBus


class TestResolveFieldName:
    def setup_method(self):
        _INJECT_CACHE.clear()

    def test_resolves_known_protocol(self):
        name = _resolve_field_name(EventBus)
        assert name == "event_bus"

    def test_raises_for_unknown_protocol(self):
        class NotAProtocol:
            pass

        with pytest.raises(TypeError, match="No binding for NotAProtocol"):
            _resolve_field_name(NotAProtocol)

    def test_error_lists_available_fields(self):
        class NotAProtocol:
            pass

        with pytest.raises(TypeError) as exc_info:
            _resolve_field_name(NotAProtocol)

        assert "event_bus" in str(exc_info.value)

    def test_cache_populated_on_first_call(self):
        assert len(_INJECT_CACHE) == 0
        _resolve_field_name(EventBus)
        assert len(_INJECT_CACHE) > 0

    def test_cache_reused_on_second_call(self):
        _resolve_field_name(EventBus)
        size_after_first = len(_INJECT_CACHE)
        _resolve_field_name(EventBus)
        assert len(_INJECT_CACHE) == size_after_first
