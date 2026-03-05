"""Tests for sync configuration builder."""

import os
from unittest.mock import patch

from airweave.platform.sync.config.base import (
    BehaviorConfig,
    CursorConfig,
    DestinationConfig,
    HandlerConfig,
    SyncConfig,
)
from airweave.platform.sync.config.builder import SyncConfigBuilder


def _clean_env():
    """Context manager to clear SYNC_CONFIG__ env vars."""
    env_copy = {k: v for k, v in os.environ.items() if not k.startswith("SYNC_CONFIG__")}
    return patch.dict(os.environ, env_copy, clear=True)


class TestSyncConfigBuilderBasic:
    """Test basic builder functionality."""

    def test_build_with_no_overrides_returns_defaults(self):
        """Test build with no overrides returns schema defaults."""
        with _clean_env():
            config = SyncConfigBuilder.build()
            assert config.destinations.skip_vespa is False  # Default: false (Vespa enabled in prod)
            assert config.handlers.enable_vector_handlers is True
            assert config.cursor.skip_load is False
            assert config.behavior.replay_from_arf is False

    def test_build_returns_sync_config_instance(self):
        """Test that build returns a SyncConfig instance."""
        config = SyncConfigBuilder.build()
        assert isinstance(config, SyncConfig)


class TestSyncConfigBuilderLayerPrecedence:
    """Test that layers are applied in correct precedence order."""

    def test_job_overrides_beat_sync(self):
        """Test that job overrides beat sync overrides."""
        config = SyncConfigBuilder.build(
            sync_overrides=SyncConfig(behavior=BehaviorConfig(skip_hash_comparison=False)),
            job_overrides=SyncConfig(behavior=BehaviorConfig(skip_hash_comparison=True)),
        )
        assert config.behavior.skip_hash_comparison is True

    def test_sync_overrides_beat_collection(self):
        """Test that sync overrides beat collection overrides."""
        config = SyncConfigBuilder.build(
            collection_overrides=SyncConfig(handlers=HandlerConfig(enable_vector_handlers=False)),
            sync_overrides=SyncConfig(handlers=HandlerConfig(enable_vector_handlers=True)),
        )
        assert config.handlers.enable_vector_handlers is True

    def test_collection_overrides_beat_env(self):
        """Test that collection overrides beat env."""
        with patch.dict(
            os.environ,
            {"SYNC_CONFIG__BEHAVIOR__SKIP_GUARDRAILS": "true"},
            clear=False,
        ):
            config = SyncConfigBuilder.build(
                collection_overrides=SyncConfig(behavior=BehaviorConfig(skip_guardrails=False))
            )
            assert config.behavior.skip_guardrails is False

    def test_env_overrides_beat_schema(self):
        """Test that env overrides beat schema defaults."""
        with patch.dict(
            os.environ,
            {"SYNC_CONFIG__BEHAVIOR__SKIP_GUARDRAILS": "true"},
            clear=False,
        ):
            config = SyncConfigBuilder.build()
            assert config.behavior.skip_guardrails is True

    def test_full_layer_chain(self):
        """Test all layers together with different fields."""
        with _clean_env():
            config = SyncConfigBuilder.build(
                collection_overrides=SyncConfig(
                    handlers=HandlerConfig(enable_vector_handlers=False)
                ),
                sync_overrides=SyncConfig(cursor=CursorConfig(skip_load=True)),
                job_overrides=SyncConfig(behavior=BehaviorConfig(replay_from_arf=True)),
            )

            assert config.handlers.enable_vector_handlers is False  # from collection
            assert config.cursor.skip_load is True  # from sync
            assert config.behavior.replay_from_arf is True  # from job


class TestSyncConfigBuilderPartialOverrides:
    """Test that partial overrides preserve other fields."""

    def test_partial_section_preserves_other_fields(self):
        """Test that overriding one field preserves others in same section."""
        with _clean_env():
            config = SyncConfigBuilder.build(
                job_overrides=SyncConfig(handlers=HandlerConfig(enable_postgres_handler=False))
            )
            assert config.handlers.enable_postgres_handler is False
            assert config.handlers.enable_vector_handlers is True  # Preserved default

    def test_partial_override_preserves_other_sections(self):
        """Test that overriding one section preserves other sections."""
        with _clean_env():
            config = SyncConfigBuilder.build(
                job_overrides=SyncConfig(
                    behavior=BehaviorConfig(skip_hash_comparison=True)
                )
            )
            assert config.behavior.skip_hash_comparison is True
            assert config.handlers.enable_vector_handlers is True  # Other section default
            assert config.cursor.skip_load is False  # Other section default

    def test_multiple_sections_independently(self):
        """Test that different sections can be overridden independently."""
        with _clean_env():
            config = SyncConfigBuilder.build(
                job_overrides=SyncConfig(
                    behavior=BehaviorConfig(skip_hash_comparison=True),
                    handlers=HandlerConfig(enable_postgres_handler=False),
                )
            )
            assert config.behavior.skip_hash_comparison is True
            assert config.handlers.enable_postgres_handler is False
            assert config.cursor.skip_load is False  # Untouched


class TestSyncConfigBuilderFromDB:
    """Test builder with DB-style inputs."""

    def test_from_db_json(self):
        """Test loading from DB JSONB column (validate dict into SyncConfig)."""
        # Simulating: SyncConfig(**collection.sync_config_json)
        db_json = {
            "handlers": {"enable_vector_handlers": False},
            "behavior": {"skip_hash_comparison": True},
        }

        with _clean_env():
            config = SyncConfigBuilder.build(
                collection_overrides=SyncConfig(**db_json)
            )
            assert config.handlers.enable_vector_handlers is False
            assert config.behavior.skip_hash_comparison is True