"""Tests for SyncExecutionConfig validation and presets."""

import warnings
from uuid import uuid4

import pytest

from airweave.platform.sync.config import SyncExecutionConfig


class TestSyncExecutionConfigValidation:
    """Test SyncExecutionConfig validators."""

    def test_invalid_destination_strategy_raises_error(self):
        """Test that invalid destination_strategy raises ValueError."""
        with pytest.raises(ValueError, match="destination_strategy must be one of"):
            SyncExecutionConfig(destination_strategy="invalid_strategy")

    def test_valid_destination_strategies(self):
        """Test all valid destination strategies are accepted."""
        valid_strategies = ["active_only", "shadow_only", "all", "active_and_shadow"]
        for strategy in valid_strategies:
            config = SyncExecutionConfig(destination_strategy=strategy)
            assert config.destination_strategy == strategy

    def test_target_destinations_overrides_strategy_warning(self):
        """Test warning when target_destinations overrides destination_strategy."""
        dest_id = uuid4()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            SyncExecutionConfig(
                target_destinations=[dest_id],
                destination_strategy="shadow_only",  # Will be ignored
            )
            assert len(w) == 1
            assert "ignored when target_destinations is set" in str(w[0].message)

    def test_no_warning_for_default_strategy_with_targets(self):
        """Test no warning when strategy is default (active_and_shadow)."""
        dest_id = uuid4()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            SyncExecutionConfig(
                target_destinations=[dest_id],
                destination_strategy="active_and_shadow",  # Default
            )
            # Should only warn about ARF re-writes, not strategy override
            assert all("destination_strategy" not in str(warning.message) for warning in w)

    def test_destination_conflict_raises_error(self):
        """Test error when same destination in target and exclude."""
        dest_id = uuid4()
        with pytest.raises(ValueError, match="Cannot have same destination"):
            SyncExecutionConfig(
                target_destinations=[dest_id],
                exclude_destinations=[dest_id],
            )

    def test_no_error_for_different_destinations(self):
        """Test no error when target and exclude are different."""
        dest1 = uuid4()
        dest2 = uuid4()
        config = SyncExecutionConfig(
            target_destinations=[dest1],
            exclude_destinations=[dest2],
        )
        assert dest1 in config.target_destinations
        assert dest2 in config.exclude_destinations

    def test_replay_with_arf_handler_warning(self):
        """Test warning when replaying but ARF handler is enabled."""
        dest_id = uuid4()
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            SyncExecutionConfig(
                target_destinations=[dest_id],
                enable_raw_data_handler=True,  # Usually disabled for replay
            )
            assert any("writing the same data to ARF again" in str(warning.message) for warning in w)

    def test_skip_cursor_updates_without_hash_warning(self):
        """Test warning about unusual cursor skip combination."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            SyncExecutionConfig(
                skip_cursor_updates=True,
                skip_hash_updates=False,  # Unusual combo
            )
            assert any("skip_cursor_updates=True but skip_hash_updates=False" in str(warning.message) for warning in w)


class TestSyncExecutionConfigPresets:
    """Test SyncExecutionConfig preset configurations."""

    def test_default_preset(self):
        """Test default() preset returns expected configuration."""
        config = SyncExecutionConfig.default()
        
        assert config.destination_strategy == "active_and_shadow"
        assert config.enable_vector_handlers is True
        assert config.enable_raw_data_handler is True
        assert config.enable_postgres_handler is True
        assert config.skip_hash_comparison is False
        assert config.skip_hash_updates is False
        assert config.skip_cursor_load is False
        assert config.skip_cursor_updates is False
        assert config.max_workers == 20
        assert config.batch_size == 100

    def test_arf_capture_only_preset(self):
        """Test arf_capture_only() disables handlers and skips cursor."""
        config = SyncExecutionConfig.arf_capture_only()
        
        # Handlers disabled except ARF
        assert config.enable_vector_handlers is False
        assert config.enable_raw_data_handler is True
        assert config.enable_postgres_handler is False
        
        # Cursor and hash skipped
        assert config.skip_hash_updates is True
        assert config.skip_cursor_load is True
        assert config.skip_cursor_updates is True

    def test_replay_to_destination_preset(self):
        """Test replay_to_destination() targets specific destination."""
        dest_id = uuid4()
        config = SyncExecutionConfig.replay_to_destination(dest_id)
        
        # Targets specific destination
        assert config.target_destinations == [dest_id]
        
        # ARF handler disabled (reading from ARF, not writing)
        assert config.enable_raw_data_handler is False
        
        # Force inserts (no hash comparison)
        assert config.skip_hash_comparison is True
        
        # Vector and postgres handlers enabled
        assert config.enable_vector_handlers is True
        assert config.enable_postgres_handler is True

    def test_dry_run_preset(self):
        """Test dry_run() disables all handlers."""
        config = SyncExecutionConfig.dry_run()
        
        # All handlers disabled
        assert config.enable_vector_handlers is False
        assert config.enable_raw_data_handler is False
        assert config.enable_postgres_handler is False
        
        # Skips hash and cursor
        assert config.skip_hash_updates is True
        assert config.skip_cursor_load is True
        assert config.skip_cursor_updates is True


class TestSyncExecutionConfigSerialization:
    """Test SyncExecutionConfig serialization for database storage."""

    def test_config_to_dict(self):
        """Test config can be serialized to dict."""
        dest_id = uuid4()
        config = SyncExecutionConfig(
            target_destinations=[dest_id],
            max_workers=50,
        )
        
        config_dict = config.model_dump()
        assert isinstance(config_dict, dict)
        assert config_dict["max_workers"] == 50
        assert dest_id in config_dict["target_destinations"]

    def test_config_from_dict(self):
        """Test config can be deserialized from dict."""
        dest_id = uuid4()
        config_dict = {
            "target_destinations": [str(dest_id)],
            "destination_strategy": "active_and_shadow",
            "enable_vector_handlers": False,
            "enable_raw_data_handler": True,
            "enable_postgres_handler": True,
            "skip_hash_comparison": False,
            "skip_hash_updates": True,
            "skip_cursor_load": True,
            "skip_cursor_updates": True,
            "max_workers": 30,
            "batch_size": 200,
        }
        
        config = SyncExecutionConfig(**config_dict)
        assert config.max_workers == 30
        assert config.batch_size == 200
        assert config.skip_cursor_load is True

    def test_preset_roundtrip(self):
        """Test preset can be serialized and deserialized."""
        original = SyncExecutionConfig.arf_capture_only()
        config_dict = original.model_dump()
        restored = SyncExecutionConfig(**config_dict)
        
        assert original.enable_vector_handlers == restored.enable_vector_handlers
        assert original.skip_cursor_load == restored.skip_cursor_load
        assert original.skip_cursor_updates == restored.skip_cursor_updates

