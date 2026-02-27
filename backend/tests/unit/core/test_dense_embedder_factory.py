"""Tests for _create_dense_embedder in the container factory."""

import types
from unittest.mock import patch

import pytest

from airweave.core.container.factory import _create_dense_embedder
from airweave.domains.embedders.dense.local import LocalDenseEmbedder
from airweave.domains.embedders.dense.mistral import MistralDenseEmbedder
from airweave.domains.embedders.dense.openai import OpenAIDenseEmbedder
from airweave.domains.embedders.registry import DenseEmbedderRegistry
from airweave.domains.embedders.registry_data import DenseEmbedderSpec


def _make_settings(**overrides):
    """Return a minimal namespace with the attrs _create_dense_embedder reads."""
    defaults = dict(
        OPENAI_API_KEY="sk-test-openai",
        MISTRAL_API_KEY="test-mistral-key",
        TEXT2VEC_INFERENCE_URL="http://localhost:9878",
    )
    defaults.update(overrides)
    return types.SimpleNamespace(**defaults)


def _build_registry(spec: DenseEmbedderSpec) -> DenseEmbedderRegistry:
    """Build a DenseEmbedderRegistry with a single patched spec."""
    registry = DenseEmbedderRegistry()
    with patch("airweave.domains.embedders.registry_data.DENSE_EMBEDDERS", [spec]):
        registry.build()
    return registry


class TestCreateDenseEmbedder:
    def test_creates_openai_embedder(self):
        spec = DenseEmbedderSpec(
            short_name="openai_small",
            name="OpenAI Small",
            description="test",
            provider="openai",
            api_model_name="text-embedding-3-small",
            max_dimensions=1536,
            max_tokens=8192,
            supports_matryoshka=True,
            embedder_class=OpenAIDenseEmbedder,
            required_setting="OPENAI_API_KEY",
        )
        registry = _build_registry(spec)
        settings = _make_settings()

        with patch(
            "airweave.core.container.factory.DENSE_EMBEDDER", "openai_small"
        ), patch("airweave.core.container.factory.EMBEDDING_DIMENSIONS", 1536):
            result = _create_dense_embedder(settings, registry)

        assert isinstance(result, OpenAIDenseEmbedder)
        assert result.dimensions == 1536
        assert result.model_name == "text-embedding-3-small"

    def test_creates_mistral_embedder(self):
        spec = DenseEmbedderSpec(
            short_name="mistral_embed",
            name="Mistral Embed",
            description="test",
            provider="mistral",
            api_model_name="mistral-embed",
            max_dimensions=1024,
            max_tokens=8192,
            supports_matryoshka=False,
            embedder_class=MistralDenseEmbedder,
            required_setting="MISTRAL_API_KEY",
        )
        registry = _build_registry(spec)
        settings = _make_settings()

        with patch(
            "airweave.core.container.factory.DENSE_EMBEDDER", "mistral_embed"
        ), patch("airweave.core.container.factory.EMBEDDING_DIMENSIONS", 1024):
            result = _create_dense_embedder(settings, registry)

        assert isinstance(result, MistralDenseEmbedder)
        assert result.dimensions == 1024
        assert result.model_name == "mistral-embed"

    def test_creates_local_embedder(self):
        spec = DenseEmbedderSpec(
            short_name="local_minilm",
            name="Local MiniLM",
            description="test",
            provider="local",
            api_model_name="sentence-transformers/all-MiniLM-L6-v2",
            max_dimensions=384,
            max_tokens=512,
            supports_matryoshka=False,
            embedder_class=LocalDenseEmbedder,
            required_setting="TEXT2VEC_INFERENCE_URL",
        )
        registry = _build_registry(spec)
        settings = _make_settings()

        with patch(
            "airweave.core.container.factory.DENSE_EMBEDDER", "local_minilm"
        ), patch("airweave.core.container.factory.EMBEDDING_DIMENSIONS", 384):
            result = _create_dense_embedder(settings, registry)

        assert isinstance(result, LocalDenseEmbedder)
        assert result.dimensions == 384

    def test_raises_for_unknown_embedder_class(self):
        class _UnknownEmbedder:
            pass

        spec = DenseEmbedderSpec(
            short_name="unknown",
            name="Unknown",
            description="test",
            provider="unknown",
            api_model_name="unknown-model",
            max_dimensions=128,
            max_tokens=512,
            supports_matryoshka=False,
            embedder_class=_UnknownEmbedder,
            required_setting=None,
        )
        registry = _build_registry(spec)
        settings = _make_settings()

        with patch(
            "airweave.core.container.factory.DENSE_EMBEDDER", "unknown"
        ), patch("airweave.core.container.factory.EMBEDDING_DIMENSIONS", 128):
            with pytest.raises(ValueError, match="Unknown dense embedder class"):
                _create_dense_embedder(settings, registry)
