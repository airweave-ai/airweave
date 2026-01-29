"""Tests for embedding configuration."""

import pytest

from airweave.core.config import settings
from airweave.platform.embedders import config as embed_config


class TestEmbeddingConfig:
    """Tests for the embedders.config module."""

    def test_get_default_provider_detects_openai(self, monkeypatch):
        """Provider detection prioritizes OpenAI when available."""
        monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test")
        monkeypatch.setattr(settings, "MISTRAL_API_KEY", "mistral-test")
        assert embed_config.get_default_provider() == "openai"

    def test_get_default_provider_falls_back_to_mistral(self, monkeypatch):
        """Provider detection falls back to Mistral when OpenAI unavailable."""
        monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
        monkeypatch.setattr(settings, "MISTRAL_API_KEY", "mistral-test")
        assert embed_config.get_default_provider() == "mistral"

    def test_get_default_provider_falls_back_to_local(self, monkeypatch):
        """Provider detection falls back to local when no API keys."""
        monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
        monkeypatch.setattr(settings, "MISTRAL_API_KEY", None)
        assert embed_config.get_default_provider() == "local"

    def test_get_provider_for_model(self):
        """Should correctly identify provider from model name."""
        assert embed_config.get_provider_for_model("mistral-embed") == "mistral"
        assert embed_config.get_provider_for_model("text-embedding-3-large") == "openai"
        assert embed_config.get_provider_for_model("text-embedding-3-small") == "openai"
        assert embed_config.get_provider_for_model("sentence-transformers/all-MiniLM-L6-v2") == "local"
        assert embed_config.get_provider_for_model("all-MiniLM-L6-v2") == "local"

    def test_get_provider_for_model_unknown(self):
        """Unknown models should return None."""
        assert embed_config.get_provider_for_model("unknown-model") is None
        assert embed_config.get_provider_for_model("") is None
        assert embed_config.get_provider_for_model(None) is None

    def test_get_default_dimensions(self, monkeypatch):
        """Default dimensions come from settings.EMBEDDING_DIMENSIONS."""
        monkeypatch.setattr(settings, "EMBEDDING_DIMENSIONS", 1024)
        assert embed_config.get_default_dimensions() == 1024

        monkeypatch.setattr(settings, "EMBEDDING_DIMENSIONS", 384)
        assert embed_config.get_default_dimensions() == 384

    def test_get_embedding_model(self, monkeypatch):
        """Should return correct model name for provider."""
        assert embed_config.get_embedding_model("openai") == "text-embedding-3-small"
        assert embed_config.get_embedding_model("mistral") == "mistral-embed"
        assert embed_config.get_embedding_model("local") == "sentence-transformers/all-MiniLM-L6-v2"

    def test_get_embedding_model_uses_default_provider(self, monkeypatch):
        """Should use default provider when none specified."""
        monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test")
        monkeypatch.setattr(settings, "MISTRAL_API_KEY", None)
        assert embed_config.get_embedding_model() == "text-embedding-3-small"

        monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
        monkeypatch.setattr(settings, "MISTRAL_API_KEY", "mistral-test")
        assert embed_config.get_embedding_model() == "mistral-embed"

    def test_is_mock_model(self):
        """Should detect mock model names."""
        assert embed_config.is_mock_model("mock-embed") is True
        assert embed_config.is_mock_model("MOCK-embedding") is True
        assert embed_config.is_mock_model("mistral-embed") is False
        assert embed_config.is_mock_model(None) is False
