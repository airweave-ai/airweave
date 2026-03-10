"""Unit tests for GitHubAuthConfig token normalisation and validation."""

import pytest
from pydantic import ValidationError

from airweave.platform.configs.auth import GitHubAuthConfig


class TestNormaliseToken:
    def test_pat_field_maps_to_token(self):
        cfg = GitHubAuthConfig.model_validate({"personal_access_token": "ghp_abc123def456"})
        assert cfg.token == "ghp_abc123def456"

    def test_access_token_field_maps_to_token(self):
        cfg = GitHubAuthConfig.model_validate({"access_token": "gho_abc123def456"})
        assert cfg.token == "gho_abc123def456"

    def test_canonical_token_field_passes_through(self):
        cfg = GitHubAuthConfig.model_validate({"token": "ghp_abc123def456"})
        assert cfg.token == "ghp_abc123def456"

    def test_missing_all_fields_raises(self):
        with pytest.raises(ValidationError):
            GitHubAuthConfig.model_validate({})

    def test_empty_string_raises(self):
        with pytest.raises(ValidationError):
            GitHubAuthConfig.model_validate({"token": ""})

    def test_whitespace_only_raises(self):
        with pytest.raises(ValidationError):
            GitHubAuthConfig.model_validate({"token": "   "})


class TestTokenFormatValidation:
    def test_classic_pat(self):
        cfg = GitHubAuthConfig(token="ghp_abcdef1234567890abcdef1234567890abcdef")
        assert cfg.token.startswith("ghp_")

    def test_fine_grained_pat(self):
        cfg = GitHubAuthConfig(token="github_pat_abcdef1234567890")
        assert cfg.token.startswith("github_pat_")

    def test_oauth_app_token(self):
        cfg = GitHubAuthConfig(token="gho_abcdef1234567890")
        assert cfg.token.startswith("gho_")

    def test_legacy_hex_token(self):
        hex_token = "a" * 40
        cfg = GitHubAuthConfig(token=hex_token)
        assert cfg.token == hex_token

    def test_invalid_format_raises(self):
        with pytest.raises(ValidationError, match="Invalid token format"):
            GitHubAuthConfig(token="bad-token-format")

    def test_strips_whitespace(self):
        cfg = GitHubAuthConfig(token="  ghp_abc123def456  ")
        assert cfg.token == "ghp_abc123def456"
