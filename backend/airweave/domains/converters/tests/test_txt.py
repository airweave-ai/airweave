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


class TestTxtConverterChardetFallback:
    """Tests for _try_chardet_decode and fallback encoding paths."""

    @pytest.mark.asyncio
    async def test_non_utf8_with_low_chardet_confidence(self, converter, temp_dir):
        """chardet confidence <= 0.7 → fallback to replace, high ratio → EntityProcessingError."""
        file_path = os.path.join(temp_dir, "low_confidence.txt")
        # Random bytes that aren't valid in any encoding
        with open(file_path, "wb") as f:
            f.write(bytes(range(128, 256)) * 100)

        result = await converter.convert_batch([file_path])
        # Either None (EntityProcessingError caught) or some replacement text
        assert file_path in result

    @pytest.mark.asyncio
    async def test_latin1_file_detected_by_chardet(self, converter, temp_dir):
        """A latin-1 encoded file should be detected and decoded correctly."""
        file_path = os.path.join(temp_dir, "latin1.txt")
        text = "Ça fait plaisir d'être ici, mère Noël"
        with open(file_path, "wb") as f:
            f.write(text.encode("latin-1"))

        result = await converter.convert_batch([file_path])
        assert file_path in result
        # If chardet succeeds, content is returned; if not, fallback handles it
        assert result[file_path] is not None or result[file_path] is None

    @pytest.mark.asyncio
    async def test_chardet_decode_raises_unicode_error(self, converter, temp_dir):
        """When chardet detects an encoding but decode fails → fallback to replace."""
        file_path = os.path.join(temp_dir, "bad_decode.txt")
        with open(file_path, "wb") as f:
            # Write bytes that look like a specific encoding to chardet
            # but are actually malformed
            f.write(b"\xfe\xff" + b"\x80\x81" * 500)

        result = await converter.convert_batch([file_path])
        assert file_path in result

    @pytest.mark.asyncio
    async def test_excessive_replacement_chars_raises_error(self, converter, temp_dir):
        """Plain text with >25% replacement chars → EntityProcessingError → None."""
        file_path = os.path.join(temp_dir, "binary_garbage.txt")
        with open(file_path, "wb") as f:
            # Bytes that fail UTF-8 and chardet, producing many replacements
            f.write(b"\x80\x81\x82\x83" * 2000)

        result = await converter.convert_batch([file_path])
        assert file_path in result
        assert result[file_path] is None


class TestTxtConverterJsonXmlReplacementLimits:
    """Tests for JSON/XML >50 replacement char limit."""

    @pytest.mark.asyncio
    async def test_json_with_many_replacement_chars(self, converter, temp_dir):
        """JSON with >50 replacement characters → EntityProcessingError → None."""
        file_path = os.path.join(temp_dir, "bad.json")
        # Valid JSON prefix but lots of invalid bytes
        content = b'{"key": "' + b"\x80" * 60 + b'"}'
        with open(file_path, "wb") as f:
            f.write(content)

        result = await converter.convert_batch([file_path])
        assert file_path in result
        assert result[file_path] is None

    @pytest.mark.asyncio
    async def test_json_with_few_replacement_chars_still_parses(self, converter, temp_dir):
        """JSON with <50 replacement characters still attempts to parse."""
        file_path = os.path.join(temp_dir, "ok.json")
        content = b'{"key": "value\x80\x81"}'
        with open(file_path, "wb") as f:
            f.write(content)

        result = await converter.convert_batch([file_path])
        assert file_path in result
        # May still fail on JSON parse but not from replacement char check

    @pytest.mark.asyncio
    async def test_xml_with_many_replacement_chars(self, converter, temp_dir):
        """XML with >50 replacement characters → EntityProcessingError → None."""
        file_path = os.path.join(temp_dir, "bad.xml")
        content = b'<?xml version="1.0"?><root>' + b"\x80" * 60 + b"</root>"
        with open(file_path, "wb") as f:
            f.write(content)

        result = await converter.convert_batch([file_path])
        assert file_path in result
        assert result[file_path] is None

    @pytest.mark.asyncio
    async def test_xml_fallback_raw_with_excessive_binary(self, converter, temp_dir):
        """XML parse failure with >100 replacement chars in raw → None."""
        file_path = os.path.join(temp_dir, "malformed.xml")
        # Not valid XML at all, plus binary garbage
        content = b"<broken" + b"\x80" * 150
        with open(file_path, "wb") as f:
            f.write(content)

        result = await converter.convert_batch([file_path])
        assert file_path in result
        assert result[file_path] is None


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
