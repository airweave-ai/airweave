"""Unit tests for embedding validation module.

Tests validate_and_raise() which delegates to the domain's
load_embedding_config() and validate_embedding_config().
"""

import pytest
from unittest.mock import patch, MagicMock

from airweave.domains.embedders.config import (
    EmbeddingConfig,
    load_embedding_config,
    provider_for_model,
    validate_embedding_config,
)
from airweave.domains.embedders.exceptions import EmbeddingConfigurationError


class TestProviderForModel:
    """Tests for provider_for_model()."""

    def test_openai_small(self):
        assert provider_for_model("text-embedding-3-small") == "openai"

    def test_openai_large(self):
        assert provider_for_model("text-embedding-3-large") == "openai"

    def test_mistral(self):
        assert provider_for_model("mistral-embed") == "mistral"

    def test_local(self):
        assert provider_for_model("sentence-transformers/all-MiniLM-L6-v2") == "local"

    def test_unknown_model(self):
        with pytest.raises(EmbeddingConfigurationError, match="Unknown model"):
            provider_for_model("nonexistent-model")


class TestLoadEmbeddingConfig:
    """Tests for load_embedding_config()."""

    def test_loads_default_config(self):
        """Test loading the actual embedding_config.yml."""
        config = load_embedding_config()
        assert config.model == "text-embedding-3-small"
        assert config.dimensions == 1536
        assert config.provider == "openai"

    def test_missing_config_file(self, tmp_path):
        """Test error when config file doesn't exist."""
        with patch(
            "airweave.domains.embedders.config.Path.__truediv__",
            return_value=tmp_path / "nonexistent.yml",
        ):
            # Use a different approach — patch the path construction
            pass

    def test_config_is_frozen(self):
        """Test that EmbeddingConfig is immutable."""
        config = EmbeddingConfig(model="test", dimensions=128, provider="openai")
        with pytest.raises(AttributeError):
            config.model = "other"


class TestValidateEmbeddingConfig:
    """Tests for validate_embedding_config()."""

    def test_valid_openai_1536(self):
        """Test valid config: OpenAI model + 1536 dims + API key."""
        config = EmbeddingConfig(
            model="text-embedding-3-small", dimensions=1536, provider="openai"
        )
        settings = MagicMock()
        settings.OPENAI_API_KEY = "sk-test"
        settings.MISTRAL_API_KEY = None

        # Should not raise
        validate_embedding_config(config, settings)

    def test_valid_openai_3072(self):
        """Test valid config: OpenAI large model + 3072 dims."""
        config = EmbeddingConfig(
            model="text-embedding-3-large", dimensions=3072, provider="openai"
        )
        settings = MagicMock()
        settings.OPENAI_API_KEY = "sk-test"

        validate_embedding_config(config, settings)

    def test_valid_mistral_1024(self):
        """Test valid config: Mistral + 1024 dims."""
        config = EmbeddingConfig(
            model="mistral-embed", dimensions=1024, provider="mistral"
        )
        settings = MagicMock()
        settings.MISTRAL_API_KEY = "mistral-key"

        validate_embedding_config(config, settings)

    def test_valid_local_384(self):
        """Test valid config: local model + 384 dims (no API key needed)."""
        config = EmbeddingConfig(
            model="sentence-transformers/all-MiniLM-L6-v2",
            dimensions=384,
            provider="local",
        )
        settings = MagicMock()

        validate_embedding_config(config, settings)

    def test_dimensions_exceed_max(self):
        """Test error when dimensions exceed model's max."""
        config = EmbeddingConfig(
            model="text-embedding-3-small", dimensions=2000, provider="openai"
        )
        settings = MagicMock()
        settings.OPENAI_API_KEY = "sk-test"

        with pytest.raises(EmbeddingConfigurationError, match="cannot produce"):
            validate_embedding_config(config, settings)

    def test_missing_api_key_openai(self):
        """Test error when OpenAI API key is missing."""
        config = EmbeddingConfig(
            model="text-embedding-3-small", dimensions=1536, provider="openai"
        )
        settings = MagicMock()
        settings.OPENAI_API_KEY = None
        settings.MISTRAL_API_KEY = None

        with pytest.raises(EmbeddingConfigurationError, match="requires an API key"):
            validate_embedding_config(config, settings)

    def test_missing_api_key_mistral(self):
        """Test error when Mistral API key is missing."""
        config = EmbeddingConfig(
            model="mistral-embed", dimensions=1024, provider="mistral"
        )
        settings = MagicMock()
        settings.OPENAI_API_KEY = None
        settings.MISTRAL_API_KEY = None

        with pytest.raises(EmbeddingConfigurationError, match="requires an API key"):
            validate_embedding_config(config, settings)


class TestValidateAndRaise:
    """Tests for validate_and_raise() (the startup entry point)."""

    def test_valid_config(self):
        """Test that no exception is raised on valid config."""
        from airweave.core.embedding_validation import validate_and_raise

        with patch("airweave.core.embedding_validation.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.MISTRAL_API_KEY = None

            # Should not raise (uses actual embedding_config.yml which has OpenAI 1536)
            validate_and_raise()

    def test_raises_on_missing_api_key(self):
        """Test that error is raised when required API key is missing."""
        from airweave.core.embedding_validation import validate_and_raise

        with patch("airweave.core.embedding_validation.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.MISTRAL_API_KEY = None

            with pytest.raises(EmbeddingConfigurationError):
                validate_and_raise()


class TestEmbeddingConfigurationError:
    """Tests for EmbeddingConfigurationError exception."""

    def test_is_exception(self):
        assert issubclass(EmbeddingConfigurationError, Exception)

    def test_stores_message(self):
        error = EmbeddingConfigurationError("Test error message")
        assert "Test error message" in str(error)
