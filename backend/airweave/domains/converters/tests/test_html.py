"""Unit tests for HtmlConverter encoding validation."""

import os
import tempfile

import pytest

from airweave.domains.converters.html import HtmlConverter


@pytest.fixture
def converter():
    return HtmlConverter()


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestHtmlConverterEncodingValidation:

    @pytest.mark.asyncio
    async def test_convert_clean_html(self, converter, temp_dir):
        file_path = os.path.join(temp_dir, "clean.html")
        html = """<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
    <h1>Hello World</h1>
    <p>This is a test paragraph.</p>
</body>
</html>
"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html)

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is not None
        assert "Hello World" in result[file_path]
        assert "test paragraph" in result[file_path]

    @pytest.mark.asyncio
    async def test_convert_empty_html(self, converter, temp_dir):
        file_path = os.path.join(temp_dir, "empty.html")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("")

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is None

    @pytest.mark.asyncio
    async def test_convert_batch_multiple_html_files(self, converter, temp_dir):
        html1_path = os.path.join(temp_dir, "page1.html")
        with open(html1_path, "w", encoding="utf-8") as f:
            f.write("<html><body><p>Page 1</p></body></html>")

        html2_path = os.path.join(temp_dir, "page2.html")
        with open(html2_path, "w", encoding="utf-8") as f:
            f.write("<html><body><p>Page 2</p></body></html>")

        result = await converter.convert_batch([html1_path, html2_path])

        assert html1_path in result
        assert html2_path in result

    @pytest.mark.asyncio
    async def test_convert_nonexistent_file(self, converter):
        result = await converter.convert_batch(["/nonexistent/page.html"])
        assert "/nonexistent/page.html" in result
        assert result["/nonexistent/page.html"] is None
