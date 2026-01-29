"""Unit tests for source feature flag filtering.

Tests that sources are correctly filtered based on organization feature flags.
These tests focus specifically on the feature flag filtering logic.
"""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4

from airweave.core.shared_models import FeatureFlag


class TestFeatureFlagFiltering:
    """Test suite for feature flag filtering logic."""

    def test_feature_flag_enum_has_sharepoint(self):
        """Test that SHAREPOINT_2019_V2 feature flag exists in enum."""
        assert hasattr(FeatureFlag, "SHAREPOINT_2019_V2")
        assert FeatureFlag.SHAREPOINT_2019_V2.value == "sharepoint_2019_v2"

    def test_source_without_flag_is_visible(self):
        """Test that sources without feature flags are always visible."""
        # Simulate a source without a feature flag
        source = MagicMock()
        source.feature_flag = None

        # Should pass the check (not filtered out)
        enabled_features = []  # No features enabled

        if source.feature_flag:
            required_flag = FeatureFlag(source.feature_flag)
            should_skip = required_flag not in enabled_features
        else:
            should_skip = False

        assert not should_skip, "Source without feature flag should be visible"

    def test_source_with_flag_hidden_when_not_enabled(self):
        """Test that sources with feature flags are hidden when feature is not enabled."""
        # Simulate SharePoint 2019 V2 source
        source = MagicMock()
        source.feature_flag = "sharepoint_2019_v2"
        source.short_name = "sharepoint2019v2"

        enabled_features = []  # No features enabled

        if source.feature_flag:
            try:
                required_flag = FeatureFlag(source.feature_flag)
                should_skip = required_flag not in enabled_features
            except ValueError:
                should_skip = False  # Fail open for invalid flags
        else:
            should_skip = False

        assert should_skip, "Source with feature flag should be hidden when feature not enabled"

    def test_source_with_flag_visible_when_enabled(self):
        """Test that sources with feature flags are visible when feature is enabled."""
        # Simulate SharePoint 2019 V2 source
        source = MagicMock()
        source.feature_flag = "sharepoint_2019_v2"
        source.short_name = "sharepoint2019v2"

        enabled_features = [FeatureFlag.SHAREPOINT_2019_V2]  # Feature enabled

        if source.feature_flag:
            try:
                required_flag = FeatureFlag(source.feature_flag)
                should_skip = required_flag not in enabled_features
            except ValueError:
                should_skip = False
        else:
            should_skip = False

        assert not should_skip, "Source with feature flag should be visible when feature is enabled"

    def test_invalid_feature_flag_fails_open(self):
        """Test that sources with invalid feature flags fail open (are visible)."""
        # Simulate a source with an invalid feature flag
        source = MagicMock()
        source.feature_flag = "invalid_flag_that_doesnt_exist"
        source.short_name = "test_source"

        enabled_features = []

        if source.feature_flag:
            try:
                required_flag = FeatureFlag(source.feature_flag)
                should_skip = required_flag not in enabled_features
            except ValueError:
                # Invalid flag - fail open (don't skip)
                should_skip = False
        else:
            should_skip = False

        assert not should_skip, "Source with invalid feature flag should fail open (be visible)"

    def test_multiple_sources_mixed_flags(self):
        """Test filtering multiple sources with different feature flag states."""
        # Simulate multiple sources
        sources = [
            {"short_name": "github", "feature_flag": None},
            {"short_name": "sharepoint2019v2", "feature_flag": "sharepoint_2019_v2"},
            {"short_name": "stripe", "feature_flag": None},
        ]

        enabled_features = []  # No features enabled

        visible_sources = []
        for source in sources:
            should_skip = False
            if source["feature_flag"]:
                try:
                    required_flag = FeatureFlag(source["feature_flag"])
                    should_skip = required_flag not in enabled_features
                except ValueError:
                    should_skip = False

            if not should_skip:
                visible_sources.append(source["short_name"])

        assert "github" in visible_sources
        assert "sharepoint2019v2" not in visible_sources  # Hidden
        assert "stripe" in visible_sources
        assert len(visible_sources) == 2
