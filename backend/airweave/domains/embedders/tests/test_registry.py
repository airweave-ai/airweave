"""Tests for dense and sparse model registries."""

import pytest

from airweave.domains.embedders.dense.registry import (
    DenseModelSpec,
    get_model_name,
    get_model_spec,
    validate_vector_size,
)
from airweave.domains.embedders.sparse.registry import (
    get_model_spec as get_sparse_model_spec,
)


class TestDenseModelSpec:
    def test_openai_small_for_1536(self):
        spec = get_model_spec("openai", 1536)
        assert spec.api_model_name == "text-embedding-3-small"
        assert spec.max_dimensions == 1536
        assert spec.supports_dimension_param is True

    def test_openai_large_for_3072(self):
        spec = get_model_spec("openai", 3072)
        assert spec.api_model_name == "text-embedding-3-large"
        assert spec.max_dimensions == 3072

    def test_openai_small_for_768(self):
        spec = get_model_spec("openai", 768)
        assert spec.api_model_name == "text-embedding-3-small"

    def test_mistral(self):
        spec = get_model_spec("mistral", 1024)
        assert spec.api_model_name == "mistral-embed"
        assert spec.supports_dimension_param is False

    def test_local(self):
        spec = get_model_spec("local", 384)
        assert spec.api_model_name == "sentence-transformers/all-MiniLM-L6-v2"

    def test_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown dense embedder provider"):
            get_model_spec("unknown", 1536)


class TestValidateVectorSize:
    def test_valid(self):
        spec = DenseModelSpec("test", 3072, 3072, True)
        validate_vector_size(spec, 1536)

    def test_exceeds_max(self):
        spec = DenseModelSpec("test", 1536, 1536, True)
        with pytest.raises(ValueError, match="cannot produce 3072"):
            validate_vector_size(spec, 3072)


class TestGetModelName:
    def test_openai(self):
        assert get_model_name("openai") == "text-embedding-3-small"

    def test_mistral(self):
        assert get_model_name("mistral") == "mistral-embed"

    def test_local(self):
        assert get_model_name("local") == "sentence-transformers/all-MiniLM-L6-v2"

    def test_unknown_falls_back_to_local(self):
        assert get_model_name("unknown") == "sentence-transformers/all-MiniLM-L6-v2"


class TestGetModelSpecByName:
    """Tests for explicit model_name lookup in get_model_spec."""

    def test_openai_small_by_name(self):
        spec = get_model_spec("openai", 1024, model_name="text-embedding-3-small")
        assert spec.api_model_name == "text-embedding-3-small"

    def test_openai_large_by_name(self):
        spec = get_model_spec("openai", 3072, model_name="text-embedding-3-large")
        assert spec.api_model_name == "text-embedding-3-large"

    def test_openai_large_with_small_dims_by_name(self):
        """Explicit name overrides the dimension heuristic."""
        spec = get_model_spec("openai", 1024, model_name="text-embedding-3-large")
        assert spec.api_model_name == "text-embedding-3-large"

    def test_mistral_by_name(self):
        spec = get_model_spec("mistral", 1024, model_name="mistral-embed")
        assert spec.api_model_name == "mistral-embed"

    def test_unknown_model_name_raises(self):
        with pytest.raises(ValueError, match="not found for provider"):
            get_model_spec("openai", 1536, model_name="nonexistent-model")

    def test_unknown_provider_with_name_raises(self):
        with pytest.raises(ValueError, match="Unknown dense embedder provider"):
            get_model_spec("unknown", 1536, model_name="test")


class TestSparseModelSpec:
    def test_fastembed(self):
        spec = get_sparse_model_spec("fastembed")
        assert spec.model_name == "Qdrant/bm25"

    def test_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown sparse embedder provider"):
            get_sparse_model_spec("unknown")
