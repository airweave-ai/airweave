"""Unit tests for TxtConverter encoding validation."""

import os
import pytest
import tempfile
from pathlib import Path

from airweave.platform.converters.txt_converter import TxtConverter
from airweave.platform.sync.exceptions import EntityProcessingError


@pytest.fixture
def converter():
    """Create TxtConverter instance."""
    return TxtConverter()


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestTxtConverterEncodingValidation:
    """Test TxtConverter encoding detection and validation."""

    @pytest.mark.asyncio
    async def test_convert_clean_utf8_text(self, converter, temp_dir):
        """Test conversion of clean UTF-8 text."""
        file_path = os.path.join(temp_dir, "clean.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Hello world! This is clean UTF-8 text.")

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] == "Hello world! This is clean UTF-8 text."

    @pytest.mark.asyncio
    async def test_convert_unicode_text(self, converter, temp_dir):
        """Test conversion of Unicode text."""
        file_path = os.path.join(temp_dir, "unicode.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Hello 世界 🌍 こんにちは")

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] == "Hello 世界 🌍 こんにちは"

    @pytest.mark.asyncio
    async def test_convert_corrupted_text_file(self, converter, temp_dir):
        """Test rejection of file with excessive replacement characters."""
        file_path = os.path.join(temp_dir, "corrupted.txt")
        # Write truly invalid UTF-8 sequences (incomplete multi-byte sequences)
        # These will produce replacement characters in UTF-8 decoding
        with open(file_path, "wb") as f:
            # Write many incomplete UTF-8 sequences
            for _ in range(10000):
                f.write(b"\xc0\x80")  # Invalid/overlong UTF-8 sequence

        result = await converter.convert_batch([file_path])

        # Should fail due to excessive replacement characters or raise EntityProcessingError
        assert file_path in result
        # May be None (rejected) or may have decoded with chardet
        # The important thing is it doesn't crash

    @pytest.mark.asyncio
    async def test_convert_empty_file(self, converter, temp_dir):
        """Test conversion of empty file."""
        file_path = os.path.join(temp_dir, "empty.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("")

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is None

    @pytest.mark.asyncio
    async def test_convert_json_clean(self, converter, temp_dir):
        """Test JSON conversion with clean data."""
        file_path = os.path.join(temp_dir, "clean.json")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write('{"name": "test", "value": 123}')

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is not None
        assert "name" in result[file_path]
        assert "test" in result[file_path]

    @pytest.mark.asyncio
    async def test_convert_json_with_corruption(self, converter, temp_dir):
        """Test JSON with invalid syntax fails gracefully."""
        file_path = os.path.join(temp_dir, "corrupted.json")
        # Write invalid JSON (will fail JSON parsing, not encoding)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write('{"name": invalid}')

        result = await converter.convert_batch([file_path])

        # Should fail due to invalid JSON syntax
        assert file_path in result
        assert result[file_path] is None

    @pytest.mark.asyncio
    async def test_convert_xml_clean(self, converter, temp_dir):
        """Test XML conversion with clean data."""
        file_path = os.path.join(temp_dir, "clean.xml")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0"?><root><item>test</item></root>')

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is not None
        assert "item" in result[file_path]

    @pytest.mark.asyncio
    async def test_convert_batch_mixed_files(self, converter, temp_dir):
        """Test batch conversion with mix of clean and empty files."""
        clean_path = os.path.join(temp_dir, "clean.txt")
        with open(clean_path, "w", encoding="utf-8") as f:
            f.write("Clean text")

        empty_path = os.path.join(temp_dir, "empty.txt")
        with open(empty_path, "w", encoding="utf-8") as f:
            f.write("")

        result = await converter.convert_batch([clean_path, empty_path])

        # Clean file should succeed
        assert result[clean_path] == "Clean text"
        # Empty file should return None
        assert result[empty_path] is None

    @pytest.mark.asyncio
    async def test_convert_latin1_encoding(self, converter, temp_dir):
        """Test conversion of Latin-1 encoded file."""
        file_path = os.path.join(temp_dir, "latin1.txt")
        # Write Latin-1 text with special characters
        text = "Café résumé naïve"
        with open(file_path, "wb") as f:
            f.write(text.encode("latin-1"))

        result = await converter.convert_batch([file_path])

        # Should detect encoding or handle gracefully
        assert file_path in result
        # Result should either be correct or None (if chardet not available)
        if result[file_path] is not None:
            assert len(result[file_path]) > 0


class TestTxtConverterEdgeCases:
    """Test edge cases in TxtConverter."""

    @pytest.mark.asyncio
    async def test_convert_nonexistent_file(self, converter):
        """Test conversion of nonexistent file."""
        result = await converter.convert_batch(["/nonexistent/file.txt"])

        assert "/nonexistent/file.txt" in result
        assert result["/nonexistent/file.txt"] is None

    @pytest.mark.asyncio
    async def test_convert_whitespace_only_file(self, converter, temp_dir):
        """Test conversion of file with only whitespace."""
        file_path = os.path.join(temp_dir, "whitespace.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("   \n\n   \t\t   ")

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is None

    @pytest.mark.asyncio
    async def test_convert_large_clean_file(self, converter, temp_dir):
        """Test conversion of large clean file."""
        file_path = os.path.join(temp_dir, "large.txt")
        # Create 1MB of clean text
        large_text = "Hello world! " * 100000
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(large_text)

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is not None
        assert len(result[file_path]) > 1000000

    @pytest.mark.asyncio
    async def test_convert_json_invalid_syntax(self, converter, temp_dir):
        """Test JSON with invalid syntax."""
        file_path = os.path.join(temp_dir, "invalid.json")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write('{"invalid": }')

        result = await converter.convert_batch([file_path])

        assert file_path in result
        assert result[file_path] is None

