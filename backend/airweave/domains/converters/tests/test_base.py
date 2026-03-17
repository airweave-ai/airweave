"""Tests for HybridDocumentConverter._try_read_as_text binary detection."""

import os
import tempfile

import pytest

from airweave.domains.converters._base import HybridDocumentConverter


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestTryReadAsText:
    """Tests for _try_read_as_text static method (binary detection)."""

    def test_plain_text_file_returns_content(self, temp_dir):
        path = os.path.join(temp_dir, "readme.docx")
        with open(path, "w", encoding="utf-8") as f:
            f.write("This is actually a plain text file with enough characters to pass threshold.")

        result = HybridDocumentConverter._try_read_as_text(path)
        assert result is not None
        assert "plain text file" in result

    def test_binary_file_returns_none(self, temp_dir):
        """File with >5% control chars → None."""
        path = os.path.join(temp_dir, "binary.docx")
        with open(path, "wb") as f:
            # Lots of control characters
            f.write(bytes(range(0, 32)) * 50)

        result = HybridDocumentConverter._try_read_as_text(path)
        assert result is None

    def test_empty_file_returns_none(self, temp_dir):
        path = os.path.join(temp_dir, "empty.docx")
        with open(path, "wb") as f:
            f.write(b"")

        result = HybridDocumentConverter._try_read_as_text(path)
        assert result is None

    def test_short_file_returns_none(self, temp_dir):
        """File with <10 chars stripped → None."""
        path = os.path.join(temp_dir, "short.docx")
        with open(path, "w", encoding="utf-8") as f:
            f.write("  hi  ")

        result = HybridDocumentConverter._try_read_as_text(path)
        assert result is None

    def test_non_utf8_returns_none(self, temp_dir):
        """Non-UTF-8 file → None."""
        path = os.path.join(temp_dir, "latin.docx")
        with open(path, "wb") as f:
            f.write(b"\xff\xfe" + "Héllo wörld".encode("utf-16-le"))

        result = HybridDocumentConverter._try_read_as_text(path)
        assert result is None

    def test_nonexistent_file_returns_none(self):
        result = HybridDocumentConverter._try_read_as_text("/nonexistent/file.docx")
        assert result is None
