"""Direct text extraction from legacy .doc (Word Binary Format) files using olefile.

The Word Binary Format stores text in an OLE2 compound document. This module
reads the ``WordDocument`` stream, parses the FIB (File Information Block) to
locate the raw text, and extracts it — handling both single-byte (cp1252) and
double-byte (UTF-16LE) encodings.

A text-offset heuristic is used: text is assumed to start immediately after the
FIB. This works for simple, non-complex documents but may produce garbage for
fast-saved or complex-format files. In those cases the extracted text falls
below the 50-character threshold, returning ``None`` so the converter layer
falls back to OCR.

A 50 MB file-size cap is enforced to keep memory bounded (~1.5x file size).
"""

from __future__ import annotations

import asyncio
import os
import struct
from typing import Optional, Tuple

from airweave.core.logging import logger
from airweave.domains.sync_pipeline.exceptions import SyncFailureError

MIN_TOTAL_CHARS = 50
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

# Character mapping for Word control codes
_CHAR_MAP = {
    0x0D: "\n",  # Paragraph mark
    0x07: "\t",  # Cell/row mark (tables)
    0x0C: "\n\n",  # Page break
    0x0B: "\n",  # Vertical tab / soft return
}


def _parse_fib(word_stream: bytes) -> Optional[Tuple[int, int, bool]]:
    """Parse the FIB header and return (text_start, ccp_text, f_encrypted).

    **Text-offset heuristic:** this function assumes text starts immediately
    after the FIB structure ends. Per the Word Binary Format spec ([MS-DOC]
    §2.5.1), text is located at the file offset given by ``fcClx`` in
    ``FibRgFcLcb97``, which points to the piece table. For simple (non-complex)
    documents created by standard Word versions the text does reside right
    after the FIB, so this heuristic works in practice.

    For complex documents, fast-saved files, or unusual structures, text may
    be at a different offset. In those cases extraction produces garbage or
    too few characters, and the caller returns ``None`` (triggering OCR
    fallback via the <50-character threshold).

    The FIB layout is:
      FibBase (32 bytes)
      + csw (2) + FibRgW (csw * 2)
      + clw (2) + FibRgLw (clw * 4)
      + cbRgFcLcb (2) + FibRgFcLcb (cbRgFcLcb * 8)
      + cswNew (2) + FibRgCswNew (cswNew * 2)  [optional]

    Returns None if the stream is not a valid Word document.
    """
    if len(word_stream) < 68:
        return None

    wIdent = struct.unpack_from("<H", word_stream, 0)[0]
    if wIdent not in (0xA5DC, 0xA5EC):
        logger.debug(f"DOC: unexpected FIB wIdent=0x{wIdent:04X}, not a valid Word document")
        return None

    flags_a = struct.unpack_from("<H", word_stream, 10)[0]
    f_encrypted = bool(flags_a & 0x0100)

    # Walk the FIB to find ccpText and compute the FIB end (= text start)
    csw = struct.unpack_from("<H", word_stream, 32)[0]
    fibrg_w_end = 34 + csw * 2

    if len(word_stream) < fibrg_w_end + 2:
        return None

    clw = struct.unpack_from("<H", word_stream, fibrg_w_end)[0]
    fibrg_lw_start = fibrg_w_end + 2
    fibrg_lw_end = fibrg_lw_start + clw * 4

    # ccpText is at offset 12 into FibRgLw97
    ccp_text_offset = fibrg_lw_start + 12
    if len(word_stream) < ccp_text_offset + 4:
        return None
    ccp_text = struct.unpack_from("<I", word_stream, ccp_text_offset)[0]

    if len(word_stream) < fibrg_lw_end + 2:
        return None

    # FibRgFcLcb — variable-length array of fc/lcb pairs
    cbRgFcLcb = struct.unpack_from("<H", word_stream, fibrg_lw_end)[0]
    fibrg_fclcb_end = fibrg_lw_end + 2 + cbRgFcLcb * 8

    # FibRgCswNew — optional trailing section
    fib_end = fibrg_fclcb_end
    if fibrg_fclcb_end + 2 <= len(word_stream):
        cswNew = struct.unpack_from("<H", word_stream, fibrg_fclcb_end)[0]
        fib_end = fibrg_fclcb_end + 2 + cswNew * 2

    text_start = fib_end

    return text_start, ccp_text, f_encrypted


def _try_decode_text(word_stream: bytes, text_start: int, ccp_text: int) -> Optional[str]:
    """Try to decode text from the WordDocument stream in cp1252, then UTF-16LE."""
    # Try single-byte (cp1252) first — most common for .doc
    text_end_1byte = text_start + ccp_text
    if text_end_1byte <= len(word_stream):
        try:
            raw = word_stream[text_start:text_end_1byte]
            text = _clean_text(raw.decode("cp1252", errors="replace"))
            if len(text.strip()) >= MIN_TOTAL_CHARS:
                return text
        except Exception:
            pass

    # Try UTF-16LE (2 bytes per char)
    text_end_2byte = text_start + ccp_text * 2
    if text_end_2byte <= len(word_stream):
        try:
            raw = word_stream[text_start:text_end_2byte]
            text = _clean_text(raw.decode("utf-16-le", errors="replace"))
            if len(text.strip()) >= MIN_TOTAL_CHARS:
                return text
        except Exception:
            pass

    return None


def _extract_text_from_word_stream(word_stream: bytes) -> Optional[str]:  # noqa: C901
    """Parse the FIB and extract the main document text from a WordDocument stream."""
    parsed = _parse_fib(word_stream)
    if parsed is None:
        return None

    text_start, ccp_text, f_encrypted = parsed

    if f_encrypted:
        logger.debug("DOC: document is encrypted, cannot extract text")
        return None

    if ccp_text == 0:
        logger.debug("DOC: ccpText is 0, empty document")
        return None

    return _try_decode_text(word_stream, text_start, ccp_text)


def _replace_char(ch: str) -> Optional[str]:
    """Map a single character through Word control code rules."""
    code = ord(ch)
    if ch in ("\n", "\t"):
        return ch
    if code in _CHAR_MAP:
        return _CHAR_MAP[code]
    if code < 0x20 and code not in (0x09, 0x0A):
        return None  # skip control characters
    if code == 0xFFFD:
        return None  # skip replacement characters from decode errors
    return ch


def _clean_text(text: str) -> str:
    """Clean extracted text by removing control characters and normalizing whitespace."""
    cleaned = [repl for ch in text if (repl := _replace_char(ch)) is not None]
    text = "".join(cleaned)

    lines = [line.rstrip() for line in text.splitlines()]
    result_lines: list[str] = []
    blank_count = 0
    for line in lines:
        if not line:
            blank_count += 1
            if blank_count <= 2:
                result_lines.append(line)
        else:
            blank_count = 0
            result_lines.append(line)

    return "\n".join(result_lines).strip()


async def extract_doc_text(path: str) -> Optional[str]:
    """Extract text from a legacy .doc file and return it as plain text.

    Returns None if extraction fails or yields fewer than MIN_TOTAL_CHARS
    characters, signalling the caller to fall back to OCR.
    """
    try:
        import olefile
    except ImportError:
        raise SyncFailureError("olefile required for .doc text extraction but not installed")

    def _extract() -> Optional[str]:
        return _extract_from_ole(path, olefile)

    return await asyncio.to_thread(_extract)


def _extract_from_ole(path: str, olefile) -> Optional[str]:  # type: ignore[no-untyped-def]
    """Synchronous OLE2 extraction logic, called via asyncio.to_thread."""
    name = os.path.basename(path)

    try:
        file_size = os.path.getsize(path)
    except OSError as exc:
        logger.warning(f"DOC {name}: cannot stat file: {exc}")
        return None

    if file_size > MAX_FILE_SIZE_BYTES:
        logger.warning(
            f"DOC {name}: file size {file_size / 1024 / 1024:.1f} MB exceeds "
            f"{MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f} MB cap, skipping"
        )
        return None

    if file_size == 0:
        logger.debug(f"DOC {name}: empty file")
        return None

    if not olefile.isOleFile(path):
        logger.debug(f"DOC {name}: not a valid OLE2 file")
        return None

    try:
        ole = olefile.OleFileIO(path)
    except Exception as exc:
        logger.warning(f"DOC {name}: failed to open OLE2 container: {exc}")
        return None

    try:
        if not ole.exists("WordDocument"):
            logger.debug(f"DOC {name}: no WordDocument stream found")
            return None

        word_stream = ole.openstream("WordDocument").read()
        text = _extract_text_from_word_stream(word_stream)

        if not text or len(text.strip()) < MIN_TOTAL_CHARS:
            chars = len(text.strip()) if text else 0
            logger.debug(f"DOC {name}: extracted {chars} chars, insufficient")
            return None

        logger.debug(f"DOC {name}: extracted {len(text.strip())} chars")
        return text

    except Exception as exc:
        logger.warning(f"DOC {name}: extraction error: {exc}")
        return None
    finally:
        ole.close()
