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

    def test_missing_config_file(self):
        """Test error when config file doesn't exist."""
        from pathlib import Path

        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(EmbeddingConfigurationError, match="not found"):
                load_embedding_config()

    def test_malformed_yaml_missing_embedding_section(self, tmp_path):
        """Test error when YAML has no 'embedding' section."""
        config_file = tmp_path / "bad_config.yml"
        config_file.write_text("something_else:\n  key: value\n")

        from pathlib import Path

        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", return_value=config_file.read_text()):
            with pytest.raises(EmbeddingConfigurationError, match="'embedding' section"):
                load_embedding_config()

    def test_malformed_yaml_missing_model(self, tmp_path):
        """Test error when YAML has no 'embedding.model'."""
        config_file = tmp_path / "bad_config.yml"
        config_file.write_text("embedding:\n  dimensions: 1536\n")

        from pathlib import Path

        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", return_value=config_file.read_text()):
            with pytest.raises(EmbeddingConfigurationError, match="'embedding.model' is required"):
                load_embedding_config()

    def test_malformed_yaml_missing_dimensions(self, tmp_path):
        """Test error when YAML has no 'embedding.dimensions'."""
        config_file = tmp_path / "bad_config.yml"
        config_file.write_text("embedding:\n  model: text-embedding-3-small\n")

        from pathlib import Path

        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", return_value=config_file.read_text()):
            with pytest.raises(
                EmbeddingConfigurationError, match="'embedding.dimensions' is required"
            ):
                load_embedding_config()

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


class TestEmbedderServiceForModel:
    """Tests for EmbedderService.for_model() classmethod."""

    def test_creates_service_for_known_model(self):
        """for_model() returns a configured service."""
        from airweave.domains.embedders.service import EmbedderService

        settings = MagicMock()
        settings.OPENAI_API_KEY = "sk-test"
        settings.MISTRAL_API_KEY = None
        settings.TEXT2VEC_INFERENCE_URL = None

        svc = EmbedderService.for_model("text-embedding-3-small", 1536, settings)

        assert svc.model_name == "text-embedding-3-small"
        assert svc.vector_size == 1536

    def test_creates_service_for_mistral(self):
        from airweave.domains.embedders.service import EmbedderService

        settings = MagicMock()
        settings.MISTRAL_API_KEY = "mistral-key"
        settings.OPENAI_API_KEY = None

        svc = EmbedderService.for_model("mistral-embed", 1024, settings)

        assert svc.model_name == "mistral-embed"
        assert svc.vector_size == 1024

    def test_raises_for_unknown_model(self):
        from airweave.domains.embedders.service import EmbedderService

        settings = MagicMock()

        with pytest.raises(EmbeddingConfigurationError, match="Unknown model"):
            EmbedderService.for_model("nonexistent-model", 1536, settings)

    def test_raises_for_missing_api_key(self):
        from airweave.domains.embedders.service import EmbedderService

        settings = MagicMock()
        settings.OPENAI_API_KEY = None
        settings.MISTRAL_API_KEY = None

        with pytest.raises(EmbeddingConfigurationError, match="requires an API key"):
            EmbedderService.for_model("text-embedding-3-small", 1536, settings)

    def test_raises_for_dimensions_exceed_max(self):
        from airweave.domains.embedders.service import EmbedderService

        settings = MagicMock()
        settings.OPENAI_API_KEY = "sk-test"

        with pytest.raises(ValueError, match="cannot produce"):
            EmbedderService.for_model("text-embedding-3-small", 9999, settings)


class TestResolveQueryEmbedder:
    """Tests for SearchFactory._resolve_query_embedder()."""

    def _make_factory(self):
        from airweave.search.factory import SearchFactory
        return SearchFactory()

    def _make_ctx(self):
        ctx = MagicMock()
        ctx.logger = MagicMock()
        return ctx

    def test_returns_global_when_collection_never_synced(self):
        """Collection without stored model uses global embedder."""
        factory = self._make_factory()
        collection = MagicMock()
        collection.embedding_model_name = None
        collection.vector_size = None

        global_embedder = MagicMock()
        global_embedder.model_name = "text-embedding-3-small"
        global_embedder.vector_size = 1536

        result = factory._resolve_query_embedder(collection, global_embedder, self._make_ctx())
        assert result is global_embedder

    def test_returns_global_when_collection_matches(self):
        """Collection matching global config reuses the cached embedder."""
        factory = self._make_factory()
        collection = MagicMock()
        collection.embedding_model_name = "text-embedding-3-small"
        collection.vector_size = 1536

        global_embedder = MagicMock()
        global_embedder.model_name = "text-embedding-3-small"
        global_embedder.vector_size = 1536

        result = factory._resolve_query_embedder(collection, global_embedder, self._make_ctx())
        assert result is global_embedder

    def test_builds_override_when_collection_differs(self):
        """Collection synced with different model builds a one-off embedder."""
        from unittest.mock import ANY

        factory = self._make_factory()
        collection = MagicMock()
        collection.embedding_model_name = "text-embedding-3-large"
        collection.vector_size = 3072

        global_embedder = MagicMock()
        global_embedder.model_name = "text-embedding-3-small"
        global_embedder.vector_size = 1536

        with patch("airweave.search.factory.EmbedderService.for_model") as mock_for_model:
            mock_for_model.return_value = MagicMock()
            mock_for_model.return_value.model_name = "text-embedding-3-large"
            mock_for_model.return_value.vector_size = 3072

            result = factory._resolve_query_embedder(
                collection, global_embedder, self._make_ctx()
            )

            mock_for_model.assert_called_once_with(
                model="text-embedding-3-large",
                dimensions=3072,
                settings=ANY,
            )
            assert result is not global_embedder


class TestChunkEmbedProcessorInstanceAttribute:
    """Test that _embedding_config_validated is an instance attribute."""

    def test_flag_is_per_instance(self):
        from airweave.platform.sync.processors.chunk_embed import ChunkEmbedProcessor

        p1 = ChunkEmbedProcessor()
        p2 = ChunkEmbedProcessor()

        p1._embedding_config_validated = True
        assert p2._embedding_config_validated is False


class TestEmbeddingConfigurationError:
    """Tests for EmbeddingConfigurationError exception."""

    def test_is_exception(self):
        assert issubclass(EmbeddingConfigurationError, Exception)

    def test_stores_message(self):
        error = EmbeddingConfigurationError("Test error message")
        assert "Test error message" in str(error)
