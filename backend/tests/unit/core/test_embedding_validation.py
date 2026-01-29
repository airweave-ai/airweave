"""Unit tests for embedding validation module."""

import pytest
from unittest.mock import patch, MagicMock


class TestGetProviderDimensions:
    """Tests for get_provider_dimensions()."""

    def test_loads_dimensions_from_defaults_yml(self):
        """Test that dimensions are loaded from defaults.yml."""
        from airweave.core.embedding_validation import get_provider_dimensions

        dims = get_provider_dimensions()

        # Should have at least openai and mistral
        assert "openai" in dims
        assert "mistral" in dims

        # OpenAI should support 1536 and 3072
        assert 1536 in dims["openai"]
        assert 3072 in dims["openai"]

        # Mistral should support 1024
        assert 1024 in dims["mistral"]

    def test_returns_sorted_dimensions(self):
        """Test that dimensions are sorted in descending order."""
        from airweave.core.embedding_validation import get_provider_dimensions

        dims = get_provider_dimensions()

        for provider, dim_list in dims.items():
            # Should be sorted descending
            assert dim_list == sorted(dim_list, reverse=True)


class TestGetAvailableProviders:
    """Tests for get_available_providers()."""

    def test_returns_openai_when_key_set(self):
        """Test OpenAI is available when API key is configured."""
        from airweave.core.embedding_validation import get_available_providers

        with patch("airweave.core.embedding_validation.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test-key"
            mock_settings.MISTRAL_API_KEY = None
            mock_settings.TEXT2VEC_INFERENCE_URL = None

            available = get_available_providers()
            assert "openai" in available

    def test_returns_mistral_when_key_set(self):
        """Test Mistral is available when API key is configured."""
        from airweave.core.embedding_validation import get_available_providers

        with patch("airweave.core.embedding_validation.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.MISTRAL_API_KEY = "mistral-test-key"
            mock_settings.TEXT2VEC_INFERENCE_URL = None

            available = get_available_providers()
            assert "mistral" in available

    def test_returns_local_when_url_set(self):
        """Test local is available when TEXT2VEC_INFERENCE_URL is set."""
        from airweave.core.embedding_validation import get_available_providers

        with patch("airweave.core.embedding_validation.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.MISTRAL_API_KEY = None
            mock_settings.TEXT2VEC_INFERENCE_URL = "http://localhost:9878"

            available = get_available_providers()
            assert "local" in available

    def test_returns_multiple_providers(self):
        """Test multiple providers can be available simultaneously."""
        from airweave.core.embedding_validation import get_available_providers

        with patch("airweave.core.embedding_validation.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.MISTRAL_API_KEY = "mistral-test"
            mock_settings.TEXT2VEC_INFERENCE_URL = "http://localhost:9878"

            available = get_available_providers()
            assert "openai" in available
            assert "mistral" in available
            assert "local" in available

    def test_returns_empty_when_no_providers_configured(self):
        """Test empty list when no providers are configured."""
        from airweave.core.embedding_validation import get_available_providers

        with patch("airweave.core.embedding_validation.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.MISTRAL_API_KEY = None
            mock_settings.TEXT2VEC_INFERENCE_URL = None

            available = get_available_providers()
            assert available == []


class TestFindCompatibleProviders:
    """Tests for find_compatible_providers()."""

    def test_finds_openai_for_1536_dims(self):
        """Test 1536 dimensions maps to OpenAI."""
        from airweave.core.embedding_validation import find_compatible_providers

        compatible = find_compatible_providers(1536)
        assert "openai" in compatible

    def test_finds_openai_for_3072_dims(self):
        """Test 3072 dimensions maps to OpenAI."""
        from airweave.core.embedding_validation import find_compatible_providers

        compatible = find_compatible_providers(3072)
        assert "openai" in compatible

    def test_finds_mistral_for_1024_dims(self):
        """Test 1024 dimensions maps to Mistral."""
        from airweave.core.embedding_validation import find_compatible_providers

        compatible = find_compatible_providers(1024)
        assert "mistral" in compatible

    def test_finds_local_for_384_dims(self):
        """Test 384 dimensions maps to local."""
        from airweave.core.embedding_validation import find_compatible_providers

        compatible = find_compatible_providers(384)
        assert "local" in compatible

    def test_returns_empty_for_unsupported_dims(self):
        """Test unsupported dimensions returns empty list."""
        from airweave.core.embedding_validation import find_compatible_providers

        # 999 is not a standard dimension for any provider
        compatible = find_compatible_providers(999)
        assert compatible == []


class TestValidateEmbeddingStack:
    """Tests for validate_embedding_stack()."""

    def test_valid_config_openai_1536(self):
        """Test valid config: OpenAI key + 1536 dimensions."""
        from airweave.core.embedding_validation import validate_embedding_stack

        with patch("airweave.core.embedding_validation.settings") as mock_settings:
            mock_settings.EMBEDDING_DIMENSIONS = 1536
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.MISTRAL_API_KEY = None
            mock_settings.TEXT2VEC_INFERENCE_URL = None

            is_valid, messages = validate_embedding_stack()

            assert is_valid is True
            # No ERROR messages
            assert not any("ERROR" in msg for msg in messages)

    def test_valid_config_mistral_1024(self):
        """Test valid config: Mistral key + 1024 dimensions."""
        from airweave.core.embedding_validation import validate_embedding_stack

        with patch("airweave.core.embedding_validation.settings") as mock_settings:
            mock_settings.EMBEDDING_DIMENSIONS = 1024
            mock_settings.OPENAI_API_KEY = None
            mock_settings.MISTRAL_API_KEY = "mistral-test"
            mock_settings.TEXT2VEC_INFERENCE_URL = None

            is_valid, messages = validate_embedding_stack()

            assert is_valid is True
            assert not any("ERROR" in msg for msg in messages)

    def test_invalid_dimension_mismatch(self):
        """Test invalid: Mistral key but 1536 dimensions (OpenAI only)."""
        from airweave.core.embedding_validation import validate_embedding_stack

        with patch("airweave.core.embedding_validation.settings") as mock_settings:
            mock_settings.EMBEDDING_DIMENSIONS = 1536
            mock_settings.OPENAI_API_KEY = None
            mock_settings.MISTRAL_API_KEY = "mistral-test"
            mock_settings.TEXT2VEC_INFERENCE_URL = None

            is_valid, messages = validate_embedding_stack()

            assert is_valid is False
            # Should have an error about dimension mismatch
            assert any("ERROR" in msg for msg in messages)

    def test_invalid_no_providers(self):
        """Test invalid: No providers configured."""
        from airweave.core.embedding_validation import validate_embedding_stack

        with patch("airweave.core.embedding_validation.settings") as mock_settings:
            mock_settings.EMBEDDING_DIMENSIONS = 1536
            mock_settings.OPENAI_API_KEY = None
            mock_settings.MISTRAL_API_KEY = None
            mock_settings.TEXT2VEC_INFERENCE_URL = None

            is_valid, messages = validate_embedding_stack()

            assert is_valid is False
            # Should have a warning about no providers
            assert any("WARNING" in msg for msg in messages)


class TestValidateAndRaise:
    """Tests for validate_and_raise()."""

    def test_raises_on_invalid_config(self):
        """Test that EmbeddingConfigurationError is raised on invalid config."""
        from airweave.core.embedding_validation import (
            EmbeddingConfigurationError,
            validate_and_raise,
        )

        with patch("airweave.core.embedding_validation.settings") as mock_settings:
            mock_settings.EMBEDDING_DIMENSIONS = 1536
            mock_settings.OPENAI_API_KEY = None
            mock_settings.MISTRAL_API_KEY = "mistral-test"
            mock_settings.TEXT2VEC_INFERENCE_URL = None

            with pytest.raises(EmbeddingConfigurationError):
                validate_and_raise()

    def test_does_not_raise_on_valid_config(self):
        """Test that no exception is raised on valid config."""
        from airweave.core.embedding_validation import validate_and_raise

        with patch("airweave.core.embedding_validation.settings") as mock_settings:
            mock_settings.EMBEDDING_DIMENSIONS = 1024
            mock_settings.OPENAI_API_KEY = None
            mock_settings.MISTRAL_API_KEY = "mistral-test"
            mock_settings.TEXT2VEC_INFERENCE_URL = None

            # Should not raise
            validate_and_raise()


class TestEmbeddingConfigurationError:
    """Tests for EmbeddingConfigurationError exception."""

    def test_is_exception(self):
        """Test that EmbeddingConfigurationError is an Exception."""
        from airweave.core.embedding_validation import EmbeddingConfigurationError

        assert issubclass(EmbeddingConfigurationError, Exception)

    def test_stores_message(self):
        """Test that error message is stored."""
        from airweave.core.embedding_validation import EmbeddingConfigurationError

        error = EmbeddingConfigurationError("Test error message")
        assert "Test error message" in str(error)
