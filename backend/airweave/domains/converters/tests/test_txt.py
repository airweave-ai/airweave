"""Unit tests for TxtConverter encoding validation."""

import os
import tempfile

import pytest

from airweave.domains.converters.txt import TxtConverter
from airweave.domains.sync_pipeline.exceptions import EntityProcessingError


@pytest.fixture
def converter():
    return TxtConverter()


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestTxtConverterEncodingValidation:

    @pytest.mark.asyncio
    async def test_convert_clean_utf8_text(self, converter, temp_dir):
        file_path = os.path.join(temp_dir, "clean.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Hello world! This is clean UTF-8 text.")

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] == "Hello world! This is clean UTF-8 text."

    @pytest.mark.asyncio
    async def test_convert_unicode_text(self, converter, temp_dir):
        file_path = os.path.join(temp_dir, "unicode.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Hello 世界 🌍 こんにちは")

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] == "Hello 世界 🌍 こんにちは"

    @pytest.mark.asyncio
    async def test_convert_corrupted_text_file(self, converter, temp_dir):
        file_path = os.path.join(temp_dir, "corrupted.txt")
        with open(file_path, "wb") as f:
            for _ in range(10000):
                f.write(b"\xc0\x80")

        result = await converter.convert_batch([file_path])
        assert file_path in result

    @pytest.mark.asyncio
    async def test_convert_empty_file(self, converter, temp_dir):
        file_path = os.path.join(temp_dir, "empty.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("")

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is None

    @pytest.mark.asyncio
    async def test_convert_json_clean(self, converter, temp_dir):
        file_path = os.path.join(temp_dir, "clean.json")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write('{"name": "test", "value": 123}')

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is not None
        assert "name" in result[file_path]

    @pytest.mark.asyncio
    async def test_convert_json_with_corruption(self, converter, temp_dir):
        file_path = os.path.join(temp_dir, "corrupted.json")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write('{"name": invalid}')

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is None

    @pytest.mark.asyncio
    async def test_convert_xml_clean(self, converter, temp_dir):
        file_path = os.path.join(temp_dir, "clean.xml")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0"?><root><item>test</item></root>')

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is not None
        assert "item" in result[file_path]

    @pytest.mark.asyncio
    async def test_convert_batch_mixed_files(self, converter, temp_dir):
        clean_path = os.path.join(temp_dir, "clean.txt")
        with open(clean_path, "w", encoding="utf-8") as f:
            f.write("Clean text")

        empty_path = os.path.join(temp_dir, "empty.txt")
        with open(empty_path, "w", encoding="utf-8") as f:
            f.write("")

        result = await converter.convert_batch([clean_path, empty_path])

        assert result[clean_path] == "Clean text"
        assert result[empty_path] is None


class TestTxtConverterEdgeCases:

    @pytest.mark.asyncio
    async def test_convert_nonexistent_file(self, converter):
        result = await converter.convert_batch(["/nonexistent/file.txt"])
        assert "/nonexistent/file.txt" in result
        assert result["/nonexistent/file.txt"] is None

    @pytest.mark.asyncio
    async def test_convert_whitespace_only_file(self, converter, temp_dir):
        file_path = os.path.join(temp_dir, "whitespace.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("   \n\n   \t\t   ")

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is None
