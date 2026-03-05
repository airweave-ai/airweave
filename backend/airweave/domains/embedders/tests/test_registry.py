"""Unit tests for DenseEmbedderRegistry and SparseEmbedderRegistry.

Table-driven tests with patched registration data.
No real platform embedders loaded.
"""

from dataclasses import dataclass, field
from unittest.mock import patch

import pytest

from airweave.domains.embedders.registry import DenseEmbedderRegistry, SparseEmbedderRegistry
from airweave.domains.embedders.registry_data import DenseEmbedderSpec, SparseEmbedderSpec

_PATCH_DENSE = "airweave.domains.embedders.registry_data.DENSE_EMBEDDERS"
_PATCH_SPARSE = "airweave.domains.embedders.registry_data.SPARSE_EMBEDDERS"


# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------


class _StubDenseEmbedder:
    """Stub dense embedder class for tests."""


class _StubDenseEmbedderAlt:
    """Second stub dense embedder class for tests."""


class _StubSparseEmbedder:
    """Stub sparse embedder class for tests."""


def _make_dense_spec(**overrides) -> DenseEmbedderSpec:
    """Build a DenseEmbedderSpec with sensible defaults, overridable."""
    defaults = {
        "short_name": "test_dense",
        "name": "Test Dense",
        "description": "A test dense embedder",
        "provider": "test_provider",
        "api_model_name": "test-model",
        "max_dimensions": 1536,
        "max_tokens": 8192,
        "supports_matryoshka": False,
        "embedder_class": _StubDenseEmbedder,
        "required_setting": None,
    }
    defaults.update(overrides)
    return DenseEmbedderSpec(**defaults)


def _make_sparse_spec(**overrides) -> SparseEmbedderSpec:
    """Build a SparseEmbedderSpec with sensible defaults, overridable."""
    defaults = {
        "short_name": "test_sparse",
        "name": "Test Sparse",
        "description": "A test sparse embedder",
        "provider": "test_provider",
        "api_model_name": "test-sparse-model",
        "embedder_class": _StubSparseEmbedder,
        "required_setting": None,
    }
    defaults.update(overrides)
    return SparseEmbedderSpec(**defaults)


def _build_dense_registry(specs: list[DenseEmbedderSpec]) -> DenseEmbedderRegistry:
    """Build a DenseEmbedderRegistry with patched registration data."""
    registry = DenseEmbedderRegistry()
    with patch(_PATCH_DENSE, specs):
        registry.build()
    return registry


def _build_sparse_registry(specs: list[SparseEmbedderSpec]) -> SparseEmbedderRegistry:
    """Build a SparseEmbedderRegistry with patched registration data."""
    registry = SparseEmbedderRegistry()
    with patch(_PATCH_SPARSE, specs):
        registry.build()
    return registry


# ===========================================================================
# DenseEmbedderRegistry — get()
# ===========================================================================


@dataclass
class DenseGetCase:
    desc: str
    specs: list = field(default_factory=list)
    query: str = "test_dense"
    expect_name: str | None = None  # None → expect KeyError


DENSE_GET_CASES = [
    DenseGetCase(
        desc="returns known entry",
        specs=[_make_dense_spec()],
        query="test_dense",
        expect_name="Test Dense",
    ),
    DenseGetCase(
        desc="unknown raises KeyError",
        specs=[_make_dense_spec()],
        query="nonexistent",
    ),
    DenseGetCase(
        desc="empty registry raises KeyError",
        specs=[],
        query="anything",
    ),
]


@pytest.mark.parametrize("case", DENSE_GET_CASES, ids=lambda c: c.desc)
def test_dense_get(case: DenseGetCase):
    registry = _build_dense_registry(case.specs)
    if case.expect_name is None:
        with pytest.raises(KeyError):
            registry.get(case.query)
    else:
        assert registry.get(case.query).name == case.expect_name


# ===========================================================================
# DenseEmbedderRegistry — list_all()
# ===========================================================================


@dataclass
class DenseListAllCase:
    desc: str
    specs: list = field(default_factory=list)
    expect_count: int = 0


DENSE_LIST_ALL_CASES = [
    DenseListAllCase(
        desc="returns all entries",
        specs=[
            _make_dense_spec(short_name="a", name="A"),
            _make_dense_spec(short_name="b", name="B"),
        ],
        expect_count=2,
    ),
    DenseListAllCase(desc="empty when no specs", specs=[], expect_count=0),
]


@pytest.mark.parametrize("case", DENSE_LIST_ALL_CASES, ids=lambda c: c.desc)
def test_dense_list_all(case: DenseListAllCase):
    registry = _build_dense_registry(case.specs)
    assert len(registry.list_all()) == case.expect_count


# ===========================================================================
# DenseEmbedderRegistry — list_for_provider()
# ===========================================================================


@dataclass
class DenseListForProviderCase:
    desc: str
    specs: list
    query_provider: str
    expect_short_names: set[str]


DENSE_LIST_FOR_PROVIDER_CASES = [
    DenseListForProviderCase(
        desc="returns matching entries",
        specs=[
            _make_dense_spec(short_name="oai_small", provider="openai"),
            _make_dense_spec(short_name="oai_large", provider="openai"),
            _make_dense_spec(short_name="mistral", provider="mistral"),
        ],
        query_provider="openai",
        expect_short_names={"oai_small", "oai_large"},
    ),
    DenseListForProviderCase(
        desc="empty for unknown provider",
        specs=[_make_dense_spec(provider="openai")],
        query_provider="nonexistent",
        expect_short_names=set(),
    ),
]


@pytest.mark.parametrize("case", DENSE_LIST_FOR_PROVIDER_CASES, ids=lambda c: c.desc)
def test_dense_list_for_provider(case: DenseListForProviderCase):
    registry = _build_dense_registry(case.specs)
    result = registry.list_for_provider(case.query_provider)
    assert {e.short_name for e in result} == case.expect_short_names


# ===========================================================================
# DenseEmbedderRegistry — entry fields
# ===========================================================================


def test_dense_entry_fields():
    """Verify all spec fields are correctly mapped to entry fields."""
    spec = _make_dense_spec(
        short_name="openai_small",
        name="OpenAI Small",
        description="Small model",
        provider="openai",
        api_model_name="text-embedding-3-small",
        max_dimensions=1536,
        max_tokens=8192,
        supports_matryoshka=True,
        embedder_class=_StubDenseEmbedder,
        required_setting="OPENAI_API_KEY",
    )
    registry = _build_dense_registry([spec])
    entry = registry.get("openai_small")

    assert entry.short_name == "openai_small"
    assert entry.name == "OpenAI Small"
    assert entry.description == "Small model"
    assert entry.class_name == "_StubDenseEmbedder"
    assert entry.provider == "openai"
    assert entry.api_model_name == "text-embedding-3-small"
    assert entry.max_dimensions == 1536
    assert entry.max_tokens == 8192
    assert entry.supports_matryoshka is True
    assert entry.embedder_class_ref is _StubDenseEmbedder
    assert entry.required_setting == "OPENAI_API_KEY"


# ===========================================================================
# DenseEmbedderRegistry — build() with real data
# ===========================================================================


def test_dense_build_real_data():
    """Build from actual DENSE_EMBEDDERS to ensure specs are valid."""
    registry = DenseEmbedderRegistry()
    registry.build()

    entries = registry.list_all()
    assert len(entries) >= 4  # openai small, openai large, mistral, local

    # Verify OpenAI small is present and correct
    oai_small = registry.get("openai_text_embedding_3_small")
    assert oai_small.provider == "openai"
    assert oai_small.api_model_name == "text-embedding-3-small"
    assert oai_small.max_dimensions == 1536
    assert oai_small.supports_matryoshka is True

    # Verify provider grouping
    openai_entries = registry.list_for_provider("openai")
    assert len(openai_entries) == 2


# ===========================================================================
# SparseEmbedderRegistry — get()
# ===========================================================================


@dataclass
class SparseGetCase:
    desc: str
    specs: list = field(default_factory=list)
    query: str = "test_sparse"
    expect_name: str | None = None


SPARSE_GET_CASES = [
    SparseGetCase(
        desc="returns known entry",
        specs=[_make_sparse_spec()],
        query="test_sparse",
        expect_name="Test Sparse",
    ),
    SparseGetCase(
        desc="unknown raises KeyError",
        specs=[_make_sparse_spec()],
        query="nonexistent",
    ),
]


@pytest.mark.parametrize("case", SPARSE_GET_CASES, ids=lambda c: c.desc)
def test_sparse_get(case: SparseGetCase):
    registry = _build_sparse_registry(case.specs)
    if case.expect_name is None:
        with pytest.raises(KeyError):
            registry.get(case.query)
    else:
        assert registry.get(case.query).name == case.expect_name


# ===========================================================================
# SparseEmbedderRegistry — list_all() and list_for_provider()
# ===========================================================================


def test_sparse_list_all():
    specs = [
        _make_sparse_spec(short_name="a", name="A"),
        _make_sparse_spec(short_name="b", name="B", provider="other"),
    ]
    registry = _build_sparse_registry(specs)
    assert len(registry.list_all()) == 2


def test_sparse_list_for_provider():
    specs = [
        _make_sparse_spec(short_name="a", provider="fastembed"),
        _make_sparse_spec(short_name="b", provider="other"),
    ]
    registry = _build_sparse_registry(specs)
    assert len(registry.list_for_provider("fastembed")) == 1
    assert len(registry.list_for_provider("nonexistent")) == 0


# ===========================================================================
# SparseEmbedderRegistry — entry fields
# ===========================================================================


def test_sparse_entry_fields():
    """Verify all spec fields are correctly mapped to entry fields."""
    spec = _make_sparse_spec(
        short_name="fastembed_bm25",
        name="FastEmbed BM25",
        description="Sparse BM25",
        provider="fastembed",
        api_model_name="Qdrant/bm25",
        embedder_class=_StubSparseEmbedder,
        required_setting=None,
    )
    registry = _build_sparse_registry([spec])
    entry = registry.get("fastembed_bm25")

    assert entry.short_name == "fastembed_bm25"
    assert entry.name == "FastEmbed BM25"
    assert entry.description == "Sparse BM25"
    assert entry.class_name == "_StubSparseEmbedder"
    assert entry.provider == "fastembed"
    assert entry.api_model_name == "Qdrant/bm25"
    assert entry.embedder_class_ref is _StubSparseEmbedder
    assert entry.required_setting is None


# ===========================================================================
# SparseEmbedderRegistry — build() with real data
# ===========================================================================


def test_sparse_build_real_data():
    """Build from actual SPARSE_EMBEDDERS to ensure specs are valid."""
    registry = SparseEmbedderRegistry()
    registry.build()

    entries = registry.list_all()
    assert len(entries) >= 1

    bm25 = registry.get("fastembed_bm25")
    assert bm25.provider == "fastembed"
    assert bm25.api_model_name == "Qdrant/bm25"
