"""Tests for EmbedderService and fakes."""

import pytest

from airweave.domains.embedders.fakes import (
    FakeDenseEmbedder,
    FakeEmbedderService,
    FakeSparseEmbedder,
)
from airweave.domains.embedders.protocols import (
    DenseEmbedderProtocol,
    EmbedderServiceProtocol,
    SparseEmbedderProtocol,
)


class TestFakeDenseEmbedder:
    @pytest.fixture
    def embedder(self):
        return FakeDenseEmbedder(vector_size=128)

    @pytest.mark.asyncio
    async def test_embed_single(self, embedder):
        result = await embedder.embed("hello world")
        assert len(result.vector) == 128

    @pytest.mark.asyncio
    async def test_embed_many(self, embedder):
        results = await embedder.embed_many(["hello", "world"])
        assert len(results) == 2
        assert all(len(r.vector) == 128 for r in results)

    @pytest.mark.asyncio
    async def test_deterministic(self, embedder):
        r1 = await embedder.embed("hello world")
        r2 = await embedder.embed("hello world")
        assert r1.vector == r2.vector

    @pytest.mark.asyncio
    async def test_different_texts_different_embeddings(self, embedder):
        r1 = await embedder.embed("hello")
        r2 = await embedder.embed("world")
        assert r1.vector != r2.vector

    def test_vector_size_property(self, embedder):
        assert embedder.vector_size == 128

    @pytest.mark.asyncio
    async def test_empty_batch(self, embedder):
        results = await embedder.embed_many([])
        assert results == []


class TestFakeSparseEmbedder:
    @pytest.fixture
    def embedder(self):
        return FakeSparseEmbedder()

    @pytest.mark.asyncio
    async def test_embed_single(self, embedder):
        result = await embedder.embed("hello world")
        assert len(result.indices) > 0
        assert len(result.indices) == len(result.values)

    @pytest.mark.asyncio
    async def test_embed_many(self, embedder):
        results = await embedder.embed_many(["hello", "world"])
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_deterministic(self, embedder):
        r1 = await embedder.embed("hello world")
        r2 = await embedder.embed("hello world")
        assert r1.indices == r2.indices
        assert r1.values == r2.values


class TestFakeEmbedderService:
    def test_model_name_default(self):
        service = FakeEmbedderService()
        assert service.model_name == "fake-model"

    def test_model_name_custom(self):
        service = FakeEmbedderService(model_name="custom-model")
        assert service.model_name == "custom-model"

    def test_vector_size(self):
        service = FakeEmbedderService(vector_size=256)
        assert service.vector_size == 256

    def test_get_dense_embedder(self):
        service = FakeEmbedderService(vector_size=256)
        embedder = service.get_dense_embedder()
        assert embedder.vector_size == 256

    def test_get_sparse_embedder(self):
        service = FakeEmbedderService()
        embedder = service.get_sparse_embedder()
        assert embedder is not None

    def test_dense_embedder_is_cached(self):
        service = FakeEmbedderService()
        e1 = service.get_dense_embedder()
        e2 = service.get_dense_embedder()
        assert e1 is e2

    def test_sparse_embedder_is_cached(self):
        service = FakeEmbedderService()
        e1 = service.get_sparse_embedder()
        e2 = service.get_sparse_embedder()
        assert e1 is e2


class TestProtocolConformance:
    """Verify fakes satisfy the runtime-checkable protocols."""

    def test_dense_protocol(self):
        assert isinstance(FakeDenseEmbedder(), DenseEmbedderProtocol)

    def test_sparse_protocol(self):
        assert isinstance(FakeSparseEmbedder(), SparseEmbedderProtocol)

    def test_service_protocol(self):
        assert isinstance(FakeEmbedderService(), EmbedderServiceProtocol)
