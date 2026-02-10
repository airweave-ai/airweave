"""Tests for sync configuration base schemas and defaults."""

import os
from unittest.mock import patch
from uuid import uuid4

import pytest

from airweave.platform.sync.config.base import (
    BehaviorConfig,
    CursorConfig,
    DestinationConfig,
    HandlerConfig,
    SyncConfig,
    _deep_merge,
)


class TestDestinationConfig:
    """Test DestinationConfig defaults and behavior."""

    def test_defaults(self):
        """Test default destination config values."""
        config = DestinationConfig()
        assert config.skip_vespa is False  # Default: false (Vespa enabled in prod)
        assert config.target_destinations is None
        assert config.exclude_destinations is None

    def test_with_custom_values(self):
        """Test destination config with custom values."""
        dest_id = uuid4()
        config = DestinationConfig(
            skip_vespa=True,
            target_destinations=[dest_id],
        )
        assert config.skip_vespa is True
        assert config.target_destinations == [dest_id]


class TestHandlerConfig:
    """Test HandlerConfig defaults and behavior."""

    def test_defaults(self):
        """Test default handler config values."""
        config = HandlerConfig()
        assert config.enable_vector_handlers is True
        assert config.enable_raw_data_handler is True
        assert config.enable_postgres_handler is True

    def test_with_custom_values(self):
        """Test handler config with custom values."""
        config = HandlerConfig(
            enable_vector_handlers=False,
            enable_postgres_handler=False,
        )
        assert config.enable_vector_handlers is False
        assert config.enable_raw_data_handler is True
        assert config.enable_postgres_handler is False


class TestCursorConfig:
    """Test CursorConfig defaults and behavior."""

    def test_defaults(self):
        """Test default cursor config values."""
        config = CursorConfig()
        assert config.skip_load is False
        assert config.skip_updates is False

    def test_with_custom_values(self):
        """Test cursor config with custom values."""
        config = CursorConfig(skip_load=True, skip_updates=True)
        assert config.skip_load is True
        assert config.skip_updates is True


class TestBehaviorConfig:
    """Test BehaviorConfig defaults and behavior."""

    def test_defaults(self):
        """Test default behavior config values."""
        config = BehaviorConfig()
        assert config.skip_hash_comparison is False
        assert config.replay_from_arf is False

    def test_with_custom_values(self):
        """Test behavior config with custom values."""
        config = BehaviorConfig(replay_from_arf=True)
        assert config.replay_from_arf is True


class TestSyncConfig:
    """Test SyncConfig composite configuration."""

    def test_defaults(self):
        """Test that SyncConfig has all sub-configs with defaults."""
        with patch.dict(os.environ, {}, clear=False):
            # Clear any SYNC_CONFIG__ vars that might be set
            env_copy = {k: v for k, v in os.environ.items() if not k.startswith("SYNC_CONFIG__")}
            with patch.dict(os.environ, env_copy, clear=True):
                config = SyncConfig()
                assert config.destinations.skip_vespa is False
                assert config.handlers.enable_vector_handlers is True
                assert config.cursor.skip_load is False
                assert config.behavior.replay_from_arf is False

    def test_with_nested_configs(self):
        """Test SyncConfig with nested sub-configs."""
        config = SyncConfig(
            handlers=HandlerConfig(enable_postgres_handler=False),
            behavior=BehaviorConfig(skip_hash_comparison=True),
        )
        assert config.handlers.enable_postgres_handler is False
        assert config.behavior.skip_hash_comparison is True

    def test_env_var_loading(self):
        """Test that SyncConfig loads from env vars."""
        with patch.dict(
            os.environ,
            {
                "SYNC_CONFIG__HANDLERS__ENABLE_VECTOR_HANDLERS": "false",
            },
            clear=False,
        ):
            config = SyncConfig()
            assert config.handlers.enable_vector_handlers is False

    def test_env_var_nested_delimiter(self):
        """Test that double underscore delimiter works correctly."""
        with patch.dict(
            os.environ,
            {"SYNC_CONFIG__BEHAVIOR__REPLAY_FROM_ARF": "true"},
            clear=False,
        ):
            config = SyncConfig()
            assert config.behavior.replay_from_arf is True


class TestSyncConfigValidation:
    """Test SyncConfig validation logic."""

    def test_destination_conflict_raises(self):
        """Test that overlapping target/exclude destinations raises ValueError."""
        dest_id = uuid4()
        with pytest.raises(ValueError, match="Destination conflict"):
            SyncConfig(
                destinations=DestinationConfig(
                    target_destinations=[dest_id],
                    exclude_destinations=[dest_id],
                )
            )

    def test_no_conflict_with_different_destinations(self):
        """Test that non-overlapping destinations don't raise."""
        config = SyncConfig(
            destinations=DestinationConfig(
                target_destinations=[uuid4()],
                exclude_destinations=[uuid4()],
            )
        )
        assert config is not None

    def test_no_conflict_with_only_target(self):
        """Test that only target destinations doesn't raise."""
        config = SyncConfig(
            destinations=DestinationConfig(target_destinations=[uuid4()])
        )
        assert config is not None

    def test_no_conflict_with_only_exclude(self):
        """Test that only exclude destinations doesn't raise."""
        config = SyncConfig(
            destinations=DestinationConfig(exclude_destinations=[uuid4()])
        )
        assert config is not None


class TestSyncConfigPresets:
    """Test SyncConfig preset factory methods."""

    def test_default_preset(self):
        """Test default() preset."""
        config = SyncConfig.default()
        assert config.destinations.skip_vespa is False  # Default: false (Vespa enabled in prod)
        assert config.handlers.enable_vector_handlers is True

    def test_vespa_only_preset(self):
        """Test vespa_only() preset uses Vespa."""
        config = SyncConfig.vespa_only()
        assert config.destinations.skip_vespa is False

    def test_arf_capture_only_preset(self):
        """Test arf_capture_only() disables vector and postgres handlers."""
        config = SyncConfig.arf_capture_only()
        assert config.handlers.enable_vector_handlers is False
        assert config.handlers.enable_raw_data_handler is True
        assert config.handlers.enable_postgres_handler is False
        assert config.cursor.skip_load is True
        assert config.cursor.skip_updates is True
        assert config.behavior.skip_hash_comparison is True

    def test_replay_from_arf_preset(self):
        """Test replay_from_arf_to_vector_dbs() preset."""
        config = SyncConfig.replay_from_arf_to_vector_dbs()
        assert config.handlers.enable_vector_handlers is True
        assert config.handlers.enable_raw_data_handler is False
        assert config.handlers.enable_postgres_handler is False
        assert config.cursor.skip_load is True
        assert config.cursor.skip_updates is True
        assert config.behavior.skip_hash_comparison is True
        assert config.behavior.replay_from_arf is True


class TestSyncConfigMerge:
    """Test SyncConfig.merge_with() method."""

    def test_merge_with_none_returns_same(self):
        """Test that merging with None returns equivalent config."""
        config = SyncConfig.default()
        merged = config.merge_with(None)
        assert merged.destinations.skip_vespa == config.destinations.skip_vespa

    def test_merge_with_empty_dict_returns_same(self):
        """Test that merging with empty dict returns equivalent config."""
        config = SyncConfig.default()
        merged = config.merge_with({})
        assert merged.destinations.skip_vespa == config.destinations.skip_vespa

    def test_merge_overwrites_values(self):
        """Test that merge overwrites specified values."""
        config = SyncConfig.default()
        merged = config.merge_with({"handlers": {"enable_postgres_handler": False}})
        assert merged.handlers.enable_postgres_handler is False
        assert merged.handlers.enable_vector_handlers is True  # Preserved

    def test_merge_deep_nested(self):
        """Test deep merge of nested values."""
        config = SyncConfig.default()
        merged = config.merge_with({
            "handlers": {"enable_postgres_handler": False},
            "behavior": {"skip_hash_comparison": True},
        })
        assert merged.handlers.enable_postgres_handler is False
        assert merged.behavior.skip_hash_comparison is True
        assert merged.handlers.enable_vector_handlers is True  # Preserved

    def test_merge_ignores_none_values(self):
        """Test that None values in overrides are ignored."""
        config = SyncConfig(behavior=BehaviorConfig(skip_hash_comparison=True))
        merged = config.merge_with({"behavior": {"skip_hash_comparison": None}})
        assert merged.behavior.skip_hash_comparison is True  # Not overwritten


class TestDeepMerge:
    """Test _deep_merge helper function."""

    def test_simple_merge(self):
        """Test simple value merge."""
        base = {"a": 1, "b": 2}
        _deep_merge(base, {"b": 3})
        assert base == {"a": 1, "b": 3}

    def test_nested_merge(self):
        """Test nested dict merge."""
        base = {"outer": {"a": 1, "b": 2}}
        _deep_merge(base, {"outer": {"b": 3}})
        assert base == {"outer": {"a": 1, "b": 3}}

    def test_ignores_none(self):
        """Test that None values are ignored."""
        base = {"a": 1}
        _deep_merge(base, {"a": None})
        assert base == {"a": 1}

    def test_adds_new_keys(self):
        """Test that new keys are added."""
        base = {"a": 1}
        _deep_merge(base, {"b": 2})
        assert base == {"a": 1, "b": 2}
