"""Unit tests for embedder configuration module."""

import pytest
from unittest.mock import patch, MagicMock


class TestGetDefaultProvider:
    """Tests for get_default_provider()."""

    def test_returns_openai_when_key_set(self):
        """Test OpenAI is default when API key is configured."""
        from airweave.platform.embedders.config import get_default_provider

        with patch("airweave.platform.embedders.config.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.MISTRAL_API_KEY = None

            provider = get_default_provider()
            assert provider == "openai"

    def test_returns_mistral_when_no_openai_key(self):
        """Test Mistral is default when no OpenAI key but Mistral is set."""
        from airweave.platform.embedders.config import get_default_provider

        with patch("airweave.platform.embedders.config.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.MISTRAL_API_KEY = "mistral-test"

            provider = get_default_provider()
            assert provider == "mistral"

    def test_returns_local_when_no_api_keys(self):
        """Test local is default when no API keys are set."""
        from airweave.platform.embedders.config import get_default_provider

        with patch("airweave.platform.embedders.config.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.MISTRAL_API_KEY = None

            provider = get_default_provider()
            assert provider == "local"

    def test_priority_openai_over_mistral(self):
        """Test OpenAI has priority over Mistral when both are set."""
        from airweave.platform.embedders.config import get_default_provider

        with patch("airweave.platform.embedders.config.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.MISTRAL_API_KEY = "mistral-test"

            provider = get_default_provider()
            assert provider == "openai"


class TestGetProviderForModel:
    """Tests for get_provider_for_model()."""

    def test_recognizes_openai_models(self):
        """Test OpenAI models are recognized."""
        from airweave.platform.embedders.config import get_provider_for_model

        assert get_provider_for_model("text-embedding-3-small") == "openai"
        assert get_provider_for_model("text-embedding-3-large") == "openai"
        assert get_provider_for_model("TEXT-EMBEDDING-3-SMALL") == "openai"

    def test_recognizes_mistral_models(self):
        """Test Mistral models are recognized."""
        from airweave.platform.embedders.config import get_provider_for_model

        assert get_provider_for_model("mistral-embed") == "mistral"
        assert get_provider_for_model("MISTRAL-EMBED") == "mistral"

    def test_recognizes_local_models(self):
        """Test local models are recognized."""
        from airweave.platform.embedders.config import get_provider_for_model

        assert get_provider_for_model("sentence-transformers/all-MiniLM-L6-v2") == "local"
        assert get_provider_for_model("all-MiniLM-L6-v2") == "local"

    def test_returns_none_for_unknown_model(self):
        """Test unknown models return None."""
        from airweave.platform.embedders.config import get_provider_for_model

        assert get_provider_for_model("unknown-model") is None

    def test_returns_none_for_empty_model(self):
        """Test empty/None model returns None."""
        from airweave.platform.embedders.config import get_provider_for_model

        assert get_provider_for_model("") is None
        assert get_provider_for_model(None) is None


class TestGetDefaultDimensions:
    """Tests for get_default_dimensions()."""

    def test_returns_settings_value(self):
        """Test returns EMBEDDING_DIMENSIONS from settings."""
        from airweave.platform.embedders.config import get_default_dimensions

        with patch("airweave.platform.embedders.config.settings") as mock_settings:
            mock_settings.EMBEDDING_DIMENSIONS = 1024

            dims = get_default_dimensions()
            assert dims == 1024

    def test_returns_different_values(self):
        """Test returns different values from settings."""
        from airweave.platform.embedders.config import get_default_dimensions

        with patch("airweave.platform.embedders.config.settings") as mock_settings:
            mock_settings.EMBEDDING_DIMENSIONS = 3072

            dims = get_default_dimensions()
            assert dims == 3072


class TestGetEmbeddingModel:
    """Tests for get_embedding_model()."""

    def test_returns_openai_model(self):
        """Test returns OpenAI model for openai provider."""
        from airweave.platform.embedders.config import get_embedding_model

        model = get_embedding_model("openai")
        assert "text-embedding" in model

    def test_returns_mistral_model(self):
        """Test returns Mistral model for mistral provider."""
        from airweave.platform.embedders.config import get_embedding_model

        model = get_embedding_model("mistral")
        assert "mistral" in model.lower()

    def test_returns_local_model(self):
        """Test returns local model for local provider."""
        from airweave.platform.embedders.config import get_embedding_model

        model = get_embedding_model("local")
        assert "MiniLM" in model or "sentence-transformers" in model

    def test_uses_default_provider_when_none(self):
        """Test uses default provider when not specified."""
        from airweave.platform.embedders.config import get_embedding_model

        with patch("airweave.platform.embedders.config.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.MISTRAL_API_KEY = None

            model = get_embedding_model()
            # Should return OpenAI model since OpenAI is default
            assert "text-embedding" in model

    def test_returns_local_for_unknown_provider(self):
        """Test returns local model for unknown provider."""
        from airweave.platform.embedders.config import get_embedding_model

        model = get_embedding_model("unknown_provider")
        # Falls back to local
        assert "MiniLM" in model or "sentence-transformers" in model


class TestIsMockModel:
    """Tests for is_mock_model()."""

    def test_recognizes_mock_models(self):
        """Test mock models are recognized."""
        from airweave.platform.embedders.config import is_mock_model

        assert is_mock_model("mock-embedding-model") is True
        assert is_mock_model("MOCK-model") is True
        assert is_mock_model("test-mock") is True

    def test_rejects_real_models(self):
        """Test real models are not recognized as mocks."""
        from airweave.platform.embedders.config import is_mock_model

        assert is_mock_model("text-embedding-3-small") is False
        assert is_mock_model("mistral-embed") is False

    def test_handles_none(self):
        """Test None returns False."""
        from airweave.platform.embedders.config import is_mock_model

        assert is_mock_model(None) is False


class TestGetDenseEmbedder:
    """Tests for get_dense_embedder() factory."""

    def test_returns_openai_embedder_for_openai_provider(self):
        """Test returns OpenAI embedder for openai provider."""
        from airweave.platform.embedders import OpenAIDenseEmbedder, get_dense_embedder

        with patch("airweave.platform.embedders.settings") as mock_settings, \
             patch("airweave.platform.embedders.OpenAIDenseEmbedder") as MockOpenAI:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.MISTRAL_API_KEY = None
            mock_settings.EMBEDDING_DIMENSIONS = 1536
            MockOpenAI.return_value = MagicMock(spec=OpenAIDenseEmbedder)

            embedder = get_dense_embedder(provider="openai")
            MockOpenAI.assert_called_once_with(vector_size=1536)

    def test_returns_mistral_embedder_for_mistral_provider(self):
        """Test returns Mistral embedder for mistral provider."""
        from airweave.platform.embedders import MistralDenseEmbedder, get_dense_embedder

        with patch("airweave.platform.embedders.settings") as mock_settings, \
             patch("airweave.platform.embedders.MistralDenseEmbedder") as MockMistral:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.MISTRAL_API_KEY = "mistral-test"
            mock_settings.EMBEDDING_DIMENSIONS = 1024
            MockMistral.return_value = MagicMock(spec=MistralDenseEmbedder)

            embedder = get_dense_embedder(provider="mistral")
            MockMistral.assert_called_once()

    def test_uses_settings_dimensions_when_not_specified(self):
        """Test uses EMBEDDING_DIMENSIONS from settings."""
        from airweave.platform.embedders import OpenAIDenseEmbedder, get_dense_embedder

        with patch("airweave.platform.embedders.settings") as mock_settings, \
             patch("airweave.platform.embedders.config.settings") as mock_config_settings, \
             patch("airweave.platform.embedders.OpenAIDenseEmbedder") as MockOpenAI:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.MISTRAL_API_KEY = None
            mock_settings.EMBEDDING_DIMENSIONS = 1536
            mock_config_settings.OPENAI_API_KEY = "sk-test"
            mock_config_settings.MISTRAL_API_KEY = None
            mock_config_settings.EMBEDDING_DIMENSIONS = 1536
            MockOpenAI.return_value = MagicMock(spec=OpenAIDenseEmbedder, VECTOR_DIMENSIONS=1536)

            get_dense_embedder()
            # Verify called with dimensions from settings
            MockOpenAI.assert_called_once_with(vector_size=1536)

    def test_uses_explicit_dimensions(self):
        """Test uses explicit dimensions when provided."""
        from airweave.platform.embedders import OpenAIDenseEmbedder, get_dense_embedder

        with patch("airweave.platform.embedders.settings") as mock_settings, \
             patch("airweave.platform.embedders.config.settings") as mock_config_settings, \
             patch("airweave.platform.embedders.OpenAIDenseEmbedder") as MockOpenAI:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.MISTRAL_API_KEY = None
            mock_settings.EMBEDDING_DIMENSIONS = 1536
            mock_config_settings.OPENAI_API_KEY = "sk-test"
            mock_config_settings.MISTRAL_API_KEY = None
            mock_config_settings.EMBEDDING_DIMENSIONS = 1536
            MockOpenAI.return_value = MagicMock(spec=OpenAIDenseEmbedder, VECTOR_DIMENSIONS=3072)

            get_dense_embedder(vector_size=3072)
            # Verify called with explicit dimensions
            MockOpenAI.assert_called_once_with(vector_size=3072)

    def test_infers_provider_from_model_name(self):
        """Test infers provider from model name."""
        from airweave.platform.embedders import MistralDenseEmbedder, get_dense_embedder

        with patch("airweave.platform.embedders.settings") as mock_settings, \
             patch("airweave.platform.embedders.MistralDenseEmbedder") as MockMistral:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.MISTRAL_API_KEY = "mistral-test"
            mock_settings.EMBEDDING_DIMENSIONS = 1024
            MockMistral.return_value = MagicMock(spec=MistralDenseEmbedder)

            get_dense_embedder(model_name="mistral-embed")
            MockMistral.assert_called_once()

    def test_raises_for_unknown_provider(self):
        """Test raises ValueError for unknown provider."""
        from airweave.platform.embedders import get_dense_embedder

        with patch("airweave.platform.embedders.settings") as mock_settings:
            mock_settings.EMBEDDING_DIMENSIONS = 1536

            with pytest.raises(ValueError) as exc_info:
                get_dense_embedder(provider="unknown_provider")

            assert "Unknown embedding provider" in str(exc_info.value)

    def test_local_uses_local_embedder(self):
        """Test local provider uses LocalDenseEmbedder."""
        from airweave.platform.embedders import LocalDenseEmbedder, get_dense_embedder

        with patch("airweave.platform.embedders.settings") as mock_settings, \
             patch("airweave.platform.embedders.config.settings") as mock_config_settings, \
             patch("airweave.platform.embedders.LocalDenseEmbedder") as MockLocal:
            mock_settings.EMBEDDING_DIMENSIONS = 384
            mock_settings.TEXT2VEC_INFERENCE_URL = "http://localhost:9878"
            mock_config_settings.EMBEDDING_DIMENSIONS = 384
            MockLocal.return_value = MagicMock(spec=LocalDenseEmbedder)

            get_dense_embedder(provider="local")
            MockLocal.assert_called_once()

    def test_local_raises_when_no_inference_url(self):
        """Test local provider raises when TEXT2VEC_INFERENCE_URL is not set."""
        from airweave.platform.embedders import get_dense_embedder
        from airweave.platform.sync.exceptions import SyncFailureError

        with patch("airweave.platform.embedders.settings") as mock_settings, \
             patch("airweave.platform.embedders.config.settings") as mock_config_settings, \
             patch("airweave.platform.embedders.local.settings") as mock_local_settings:
            mock_settings.EMBEDDING_DIMENSIONS = 384
            mock_config_settings.EMBEDDING_DIMENSIONS = 384
            mock_local_settings.TEXT2VEC_INFERENCE_URL = None

            with pytest.raises(SyncFailureError) as exc_info:
                get_dense_embedder(provider="local")

            assert "TEXT2VEC_INFERENCE_URL" in str(exc_info.value)
