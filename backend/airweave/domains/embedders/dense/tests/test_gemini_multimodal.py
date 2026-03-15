"""Unit tests for GeminiDenseEmbedder multimodal (embed_file) support.

All Google GenAI SDK interactions are mocked — no network calls.
"""

import math
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.domains.embedders.dense.gemini import (
    GeminiDenseEmbedder,
    _MULTIMODAL_MIME_TYPES,
    _get_max_file_size_bytes,
    _get_max_pdf_pages,
)
from airweave.domains.embedders.exceptions import (
    EmbedderAuthError,
    EmbedderConnectionError,
    EmbedderInputError,
    EmbedderProviderError,
    EmbedderRateLimitError,
    EmbedderTimeoutError,
)
from airweave.domains.embedders.protocols import EmbeddingPurpose

_DIMS = 256
_MODEL = "gemini-embedding-2-preview"
_API_KEY = "test-gemini-key"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_embedding_object(vector: list[float]) -> SimpleNamespace:
    return SimpleNamespace(values=vector)


def _make_response(vectors: list[list[float]]) -> SimpleNamespace:
    return SimpleNamespace(embeddings=[_make_embedding_object(v) for v in vectors])


def _make_embedder(**overrides) -> GeminiDenseEmbedder:
    defaults = {"api_key": _API_KEY, "model": _MODEL, "dimensions": _DIMS}
    defaults.update(overrides)
    with patch("airweave.domains.embedders.dense.gemini.genai.Client"):
        return GeminiDenseEmbedder(**defaults)


# ---------------------------------------------------------------------------
# Multimodal properties
# ---------------------------------------------------------------------------


class TestMultimodalProperties:
    def test_supports_multimodal(self):
        embedder = _make_embedder()
        assert embedder.supports_multimodal is True

    def test_supported_mime_types(self):
        embedder = _make_embedder()
        assert embedder.supported_mime_types == _MULTIMODAL_MIME_TYPES
        assert "image/png" in embedder.supported_mime_types
        assert "application/pdf" in embedder.supported_mime_types
        assert "audio/mpeg" in embedder.supported_mime_types
        assert "video/mp4" in embedder.supported_mime_types


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------


class TestFileValidation:
    def test_unsupported_mime_type(self):
        embedder = _make_embedder()
        with pytest.raises(EmbedderInputError, match="Unsupported MIME type"):
            embedder._validate_file_input("/tmp/test.txt", "text/plain")

    def test_file_not_found(self):
        embedder = _make_embedder()
        with pytest.raises(EmbedderInputError, match="File not found"):
            embedder._validate_file_input("/nonexistent/file.png", "image/png")

    def test_file_too_large(self, tmp_path):
        max_bytes = _get_max_file_size_bytes()
        large_file = tmp_path / "big.png"
        large_file.write_bytes(b"\x00" * (max_bytes + 1))
        embedder = _make_embedder()
        with pytest.raises(EmbedderInputError, match="exceeds limit"):
            embedder._validate_file_input(str(large_file), "image/png")

    def test_empty_file(self, tmp_path):
        empty_file = tmp_path / "empty.png"
        empty_file.write_bytes(b"")
        embedder = _make_embedder()
        with pytest.raises(EmbedderInputError, match="File is empty"):
            embedder._validate_file_input(str(empty_file), "image/png")

    def test_valid_image_file(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG" + b"\x00" * 100)
        embedder = _make_embedder()
        # Should not raise
        embedder._validate_file_input(str(img), "image/png")

    def test_pdf_page_validation_over_limit(self, tmp_path):
        embedder = _make_embedder()
        pdf_path = tmp_path / "big.pdf"
        pdf_path.write_bytes(b"\x00" * 100)

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=_get_max_pdf_pages() + 1)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            with pytest.raises(EmbedderInputError, match="pages.*exceeding"):
                embedder._validate_pdf_pages(str(pdf_path))

    def test_pdf_page_validation_at_limit(self, tmp_path):
        embedder = _make_embedder()
        pdf_path = tmp_path / "ok.pdf"
        pdf_path.write_bytes(b"\x00" * 100)

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=_get_max_pdf_pages())
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        mock_fitz = MagicMock()
        mock_fitz.open.return_value = mock_doc

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            # Should not raise — exactly at limit
            embedder._validate_pdf_pages(str(pdf_path))

    def test_pdf_read_failure(self, tmp_path):
        embedder = _make_embedder()
        pdf_path = tmp_path / "corrupt.pdf"
        pdf_path.write_bytes(b"\x00" * 100)

        mock_fitz = MagicMock()
        mock_fitz.open.side_effect = RuntimeError("corrupt PDF")

        with patch.dict("sys.modules", {"fitz": mock_fitz}):
            with pytest.raises(EmbedderInputError, match="Failed to read PDF"):
                embedder._validate_pdf_pages(str(pdf_path))


# ---------------------------------------------------------------------------
# embed_file
# ---------------------------------------------------------------------------


class TestEmbedFile:
    @pytest.mark.asyncio
    async def test_embed_file_image(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG" + b"\x00" * 100)

        vector = [float(i) for i in range(_DIMS)]
        response = _make_response([vector])

        embedder = _make_embedder()
        embedder._client.aio.models.embed_content = AsyncMock(return_value=response)

        result = await embedder.embed_file(str(img), "image/png")

        assert len(result.vector) == _DIMS
        # Verify the API was called with a Part containing inline_data
        call_kwargs = embedder._client.aio.models.embed_content.call_args
        contents = call_kwargs.kwargs.get("contents") or call_kwargs[1].get("contents")
        assert len(contents) == 1

    @pytest.mark.asyncio
    async def test_embed_file_pdf(self, tmp_path):
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4" + b"\x00" * 100)

        vector = [float(i) for i in range(_DIMS)]
        response = _make_response([vector])

        embedder = _make_embedder()
        embedder._client.aio.models.embed_content = AsyncMock(return_value=response)

        # Mock PDF page validation
        with patch.object(embedder, "_validate_pdf_pages"):
            result = await embedder.embed_file(str(pdf), "application/pdf")

        assert len(result.vector) == _DIMS

    @pytest.mark.asyncio
    async def test_embed_file_uses_document_purpose_by_default(self, tmp_path):
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)

        response = _make_response([[0.0] * _DIMS])
        embedder = _make_embedder()
        embedder._client.aio.models.embed_content = AsyncMock(return_value=response)

        await embedder.embed_file(str(img), "image/jpeg")

        call_kwargs = embedder._client.aio.models.embed_content.call_args
        config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
        assert config["task_type"] == "RETRIEVAL_DOCUMENT"

    @pytest.mark.asyncio
    async def test_embed_file_with_query_purpose(self, tmp_path):
        img = tmp_path / "test.jpg"
        img.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)

        response = _make_response([[0.0] * _DIMS])
        embedder = _make_embedder()
        embedder._client.aio.models.embed_content = AsyncMock(return_value=response)

        await embedder.embed_file(str(img), "image/jpeg", purpose=EmbeddingPurpose.QUERY)

        call_kwargs = embedder._client.aio.models.embed_content.call_args
        config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
        assert config["task_type"] == "RETRIEVAL_QUERY"

    @pytest.mark.asyncio
    async def test_embed_file_l2_normalization(self, tmp_path):
        """Matryoshka truncation triggers L2 normalization."""
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG" + b"\x00" * 100)

        vector = [3.0, 4.0] + [0.0] * (_DIMS - 2)
        response = _make_response([vector])

        embedder = _make_embedder()
        embedder._client.aio.models.embed_content = AsyncMock(return_value=response)

        result = await embedder.embed_file(str(img), "image/png")

        norm = math.sqrt(sum(x * x for x in result.vector))
        assert abs(norm - 1.0) < 1e-6

    @pytest.mark.asyncio
    async def test_embed_file_unsupported_mime(self, tmp_path):
        txt = tmp_path / "test.txt"
        txt.write_bytes(b"hello")

        embedder = _make_embedder()
        with pytest.raises(EmbedderInputError, match="Unsupported MIME type"):
            await embedder.embed_file(str(txt), "text/plain")

    @pytest.mark.asyncio
    async def test_embed_file_not_found(self):
        embedder = _make_embedder()
        with pytest.raises(EmbedderInputError, match="File not found"):
            await embedder.embed_file("/nonexistent.png", "image/png")


# ---------------------------------------------------------------------------
# Multimodal API error translation
# ---------------------------------------------------------------------------


class TestMultimodalApiErrors:
    @pytest.mark.asyncio
    async def test_auth_error(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG" + b"\x00" * 100)

        embedder = _make_embedder()
        exc = MagicMock(spec=Exception)
        exc.code = 401
        client_error = type("ClientError", (Exception,), {"code": 401})()
        embedder._client.aio.models.embed_content = AsyncMock(side_effect=client_error)

        with patch("airweave.domains.embedders.dense.gemini.errors") as mock_errors:
            mock_errors.ClientError = type(client_error)
            mock_errors.ServerError = type("ServerError", (Exception,), {})
            with pytest.raises(EmbedderAuthError):
                await embedder.embed_file(str(img), "image/png")

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG" + b"\x00" * 100)

        embedder = _make_embedder()
        client_error = type("ClientError", (Exception,), {"code": 429})()
        embedder._client.aio.models.embed_content = AsyncMock(side_effect=client_error)

        with patch("airweave.domains.embedders.dense.gemini.errors") as mock_errors:
            mock_errors.ClientError = type(client_error)
            mock_errors.ServerError = type("ServerError", (Exception,), {})
            with pytest.raises(EmbedderRateLimitError):
                await embedder.embed_file(str(img), "image/png")

    @pytest.mark.asyncio
    async def test_timeout_error(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG" + b"\x00" * 100)

        embedder = _make_embedder()
        embedder._client.aio.models.embed_content = AsyncMock(side_effect=TimeoutError("timeout"))

        with patch("airweave.domains.embedders.dense.gemini.errors") as mock_errors:
            mock_errors.ClientError = type("ClientError", (Exception,), {})
            mock_errors.ServerError = type("ServerError", (Exception,), {})
            with pytest.raises(EmbedderTimeoutError):
                await embedder.embed_file(str(img), "image/png")

    @pytest.mark.asyncio
    async def test_connection_error(self, tmp_path):
        img = tmp_path / "test.png"
        img.write_bytes(b"\x89PNG" + b"\x00" * 100)

        embedder = _make_embedder()
        embedder._client.aio.models.embed_content = AsyncMock(
            side_effect=ConnectionError("refused")
        )

        with patch("airweave.domains.embedders.dense.gemini.errors") as mock_errors:
            mock_errors.ClientError = type("ClientError", (Exception,), {})
            mock_errors.ServerError = type("ServerError", (Exception,), {})
            with pytest.raises(EmbedderConnectionError):
                await embedder.embed_file(str(img), "image/png")


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    def test_multimodal_protocol_isinstance(self):
        from airweave.domains.embedders.protocols import MultimodalDenseEmbedderProtocol

        embedder = _make_embedder()
        assert isinstance(embedder, MultimodalDenseEmbedderProtocol)

    def test_fake_multimodal_protocol_isinstance(self):
        from airweave.domains.embedders.fakes.embedder import FakeMultimodalDenseEmbedder
        from airweave.domains.embedders.protocols import MultimodalDenseEmbedderProtocol

        fake = FakeMultimodalDenseEmbedder(dimensions=256)
        assert isinstance(fake, MultimodalDenseEmbedderProtocol)

    def test_fake_dense_not_multimodal(self):
        from airweave.domains.embedders.fakes.embedder import FakeDenseEmbedder
        from airweave.domains.embedders.protocols import MultimodalDenseEmbedderProtocol

        fake = FakeDenseEmbedder(dimensions=256)
        assert not isinstance(fake, MultimodalDenseEmbedderProtocol)
