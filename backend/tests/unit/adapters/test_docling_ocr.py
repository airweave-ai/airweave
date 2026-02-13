"""Tests for DoclingOcrAdapter."""

from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from airweave.adapters.ocr.docling import DoclingOcrAdapter
from airweave.core.protocols.ocr import OcrProvider


class TestProtocolConformance:
    def test_docling_is_ocr_provider(self):
        adapter = DoclingOcrAdapter(base_url="http://docling:5001")
        assert isinstance(adapter, OcrProvider)


@dataclass
class Case:
    desc: str

    response_status: int = 200
    response_json: Optional[dict] = field(default_factory=lambda: {
        "document": {"md_content": "# Hello from Docling"},
        "status": "success",
    })
    raise_exception: Optional[Exception] = None

    expect_result: Optional[str] = "# Hello from Docling"
    expect_raises: bool = False


CASES = [
    Case(
        desc="successful conversion returns markdown",
    ),
    Case(
        desc="empty markdown returns None",
        response_json={"document": {"md_content": ""}, "status": "success"},
        expect_result=None,
    ),
    Case(
        desc="missing document key returns None",
        response_json={"status": "success"},
        expect_result=None,
    ),
    Case(
        desc="HTTP error raises",
        response_status=500,
        response_json={"error": "internal"},
        expect_raises=True,
    ),
    Case(
        desc="timeout raises",
        raise_exception=httpx.ReadTimeout("timed out"),
        expect_raises=True,
    ),
    Case(
        desc="connection error raises",
        raise_exception=httpx.ConnectError("refused"),
        expect_raises=True,
    ),
]


def _build_mock_response(case: Case) -> httpx.Response:
    """Build a mock httpx.Response from a test case."""
    response = httpx.Response(
        status_code=case.response_status,
        json=case.response_json,
        request=httpx.Request("POST", "http://docling:5001/v1/convert/file"),
    )
    return response


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_docling_ocr(case: Case, tmp_path):
    test_file = tmp_path / "doc.pdf"
    test_file.write_bytes(b"%PDF-1.4 fake content")

    adapter = DoclingOcrAdapter(base_url="http://docling:5001")

    mock_post = AsyncMock()
    if case.raise_exception:
        mock_post.side_effect = case.raise_exception
    else:
        mock_post.return_value = _build_mock_response(case)

    with patch("airweave.adapters.ocr.docling.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        if case.expect_raises:
            with pytest.raises(Exception):
                await adapter.convert_batch([str(test_file)])
        else:
            result = await adapter.convert_batch([str(test_file)])
            assert result.get(str(test_file)) == case.expect_result


@pytest.mark.asyncio
async def test_unsupported_extension(tmp_path):
    """Unsupported file extensions return None without calling the API."""
    test_file = tmp_path / "data.xyz"
    test_file.write_text("unsupported")

    adapter = DoclingOcrAdapter(base_url="http://docling:5001")

    with patch("airweave.adapters.ocr.docling.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await adapter.convert_batch([str(test_file)])
        assert result[str(test_file)] is None
        mock_client.post.assert_not_called()
