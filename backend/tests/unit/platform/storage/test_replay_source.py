"""Unit tests for ArfReplaySource attribute naming."""

from uuid import uuid4

from airweave.platform.storage.replay_source import ArfReplaySource


class TestArfReplaySourceAttributes:
    """Verify ArfReplaySource uses BaseSource-compatible attribute names."""

    def test_class_defaults_use_public_names(self):
        assert ArfReplaySource.short_name == "arf_replay"
        assert ArfReplaySource.source_name == "ARF Replay"

    def test_fallback_when_no_original(self):
        source = ArfReplaySource(sync_id=uuid4())

        assert source.short_name == "arf_replay"
        assert source.source_name == "ARF Replay"

    def test_masquerade_overrides_instance(self):
        source = ArfReplaySource(sync_id=uuid4(), original_short_name="slack")

        assert source.short_name == "slack"
        assert source.source_name == "ARF Replay (slack)"

    def test_masquerade_does_not_mutate_class(self):
        ArfReplaySource(sync_id=uuid4(), original_short_name="github")

        assert ArfReplaySource.short_name == "arf_replay"
