"""Tests for legacy .doc text extraction via olefile."""

import os
import struct
import tempfile

import pytest

from airweave.domains.converters.text_extractors.doc import (
    MAX_FILE_SIZE_BYTES,
    _clean_text,
    _extract_text_from_word_stream,
    extract_doc_text,
)
from airweave.platform.sources.file_stub import _build_ole2_doc


def _write_tmp(data: bytes, suffix: str = ".doc") -> str:
    """Write bytes to a temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.write(fd, data)
    os.close(fd)
    return path


class TestExtractTextFromWordStream:
    """Unit tests for the low-level FIB parser."""

    def _make_word_stream(self, text: str) -> bytes:
        """Build a minimal WordDocument stream with the given text at offset 512."""
        text_bytes = text.encode("cp1252", errors="replace")
        ccp_text = len(text_bytes)

        fib_base = bytearray(32)
        struct.pack_into("<H", fib_base, 0, 0xA5EC)  # wIdent
        struct.pack_into("<H", fib_base, 2, 193)  # nFib
        struct.pack_into("<H", fib_base, 10, 0x0000)  # flags

        csw = 14
        fibrg_w = bytearray(csw * 2)
        clw = 22
        fibrg_lw = bytearray(clw * 4)
        struct.pack_into("<I", fibrg_lw, 12, ccp_text)

        fib = (
            bytes(fib_base)
            + struct.pack("<H", csw)
            + bytes(fibrg_w)
            + struct.pack("<H", clw)
            + bytes(fibrg_lw)
            + struct.pack("<H", 0)
        )
        return fib.ljust(512, b"\x00") + text_bytes

    def test_extract_basic_text(self):
        text = "This is a test document with enough meaningful content to pass the threshold.\r"
        ws = self._make_word_stream(text)
        result = _extract_text_from_word_stream(ws)
        assert result is not None
        assert "test document" in result

    def test_extract_empty_text(self):
        ws = self._make_word_stream("")
        result = _extract_text_from_word_stream(ws)
        assert result is None

    def test_extract_below_threshold(self):
        ws = self._make_word_stream("tiny")
        result = _extract_text_from_word_stream(ws)
        assert result is None

    def test_extract_stream_too_short(self):
        result = _extract_text_from_word_stream(b"\x00" * 100)
        assert result is None

    def test_extract_bad_magic(self):
        text = "enough content to be above fifty chars for extraction"
        ws = self._make_word_stream(text)
        ws_bad = bytearray(ws)
        struct.pack_into("<H", ws_bad, 0, 0x0000)  # invalid wIdent
        result = _extract_text_from_word_stream(bytes(ws_bad))
        assert result is None

    def test_extract_encrypted_document(self):
        text = "enough content to be above fifty chars for extraction"
        ws = bytearray(self._make_word_stream(text))
        # Set fEncrypted flag (bit 8 of flags at offset 10)
        flags = struct.unpack_from("<H", ws, 10)[0]
        struct.pack_into("<H", ws, 10, flags | 0x0100)
        result = _extract_text_from_word_stream(bytes(ws))
        assert result is None

    def test_extract_multiline_content(self):
        text = (
            "Paragraph one with enough content.\r"
            "Paragraph two with more text.\r"
            "Paragraph three adds detail.\r"
        )
        ws = self._make_word_stream(text)
        result = _extract_text_from_word_stream(ws)
        assert result is not None
        assert "Paragraph one" in result
        assert "Paragraph two" in result


class TestCleanText:
    def test_removes_control_chars(self):
        text = "Hello\x01\x02\x03World"
        result = _clean_text(text)
        assert result == "HelloWorld"

    def test_preserves_tabs_and_newlines(self):
        text = "Line 1\nLine 2\tTabbed"
        result = _clean_text(text)
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Tabbed" in result

    def test_collapses_excessive_blank_lines(self):
        text = "Line 1\n\n\n\n\n\n\nLine 2"
        result = _clean_text(text)
        # Should collapse to at most 2 consecutive blank lines (3 newlines)
        assert "\n\n\n\n" not in result
        assert "Line 1" in result
        assert "Line 2" in result

    def test_word_paragraph_separator(self):
        text = "Para 1\rPara 2"
        result = _clean_text(text)
        assert "Para 1" in result
        assert "Para 2" in result


class TestExtractDocText:
    """Integration tests using _build_ole2_doc to create valid .doc files."""

    @pytest.mark.asyncio
    async def test_extract_from_generated_doc(self):
        """Round-trip: generate a .doc, extract text, verify content."""
        text = (
            "This document contains a unique tracking token abc12345 "
            "and enough text to meet the minimum threshold.\r"
        )
        doc_bytes = _build_ole2_doc(text.encode("cp1252"))
        path = _write_tmp(doc_bytes)
        try:
            result = await extract_doc_text(path)
            assert result is not None
            assert "abc12345" in result
            assert "tracking token" in result
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_extract_empty_file(self):
        path = _write_tmp(b"")
        try:
            result = await extract_doc_text(path)
            assert result is None
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_extract_corrupted_file(self):
        path = _write_tmp(os.urandom(1024))
        try:
            result = await extract_doc_text(path)
            assert result is None
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_extract_non_ole_file(self):
        """Plain text file renamed to .doc should return None."""
        path = _write_tmp(b"This is just plain text, not an OLE2 file.")
        try:
            result = await extract_doc_text(path)
            assert result is None
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_extract_oversized_file(self, tmp_path):
        """Files exceeding MAX_FILE_SIZE_BYTES should be skipped without parsing."""
        large_file = tmp_path / "huge.doc"
        # Create a sparse file that reports > 50MB
        large_file.write_bytes(b"\x00")
        original_max = MAX_FILE_SIZE_BYTES

        # Temporarily set a tiny cap to test the guard without creating a 50MB file
        import airweave.domains.converters.text_extractors.doc as doc_module

        doc_module.MAX_FILE_SIZE_BYTES = 10
        try:
            # Write a small but > 10 byte file
            large_file.write_bytes(b"\x00" * 20)
            result = await extract_doc_text(str(large_file))
            assert result is None
        finally:
            doc_module.MAX_FILE_SIZE_BYTES = original_max

    @pytest.mark.asyncio
    async def test_extract_nonexistent_file(self):
        result = await extract_doc_text("/nonexistent/path/fake.doc")
        assert result is None
