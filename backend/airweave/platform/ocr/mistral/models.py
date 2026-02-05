"""Typed dataclasses for tracking files through the Mistral OCR pipeline.

Every function in the ``mistral`` package returns one of these types -- no raw
tuples or dicts leak across module boundaries.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

# Image extensions that Mistral treats as ``image_url`` (vs ``document_url``).
IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png"})
DOCUMENT_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".docx", ".pptx"})
SUPPORTED_EXTENSIONS: frozenset[str] = IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS


# ======================================================================
# Preparation phase
# ======================================================================


@dataclass(frozen=True)
class FileChunk:
    """A single chunk of a document ready for Mistral OCR.

    Attributes:
        original_path: The path the caller passed in.
        chunk_path: The actual file to process (may be a temp split/compressed copy).
        batch_index: Position in the original ``file_paths`` list (handles duplicates).
        chunk_index: 0-based index within the split of this file.
        is_temp: ``True`` if *chunk_path* is a temp file we created and must clean up.
    """

    original_path: str
    chunk_path: str
    batch_index: int
    chunk_index: int = 0
    is_temp: bool = False

    @property
    def file_name(self) -> str:
        """Base file name derived from the original path."""
        return os.path.basename(self.original_path)

    @property
    def extension(self) -> str:
        """Lowercase file extension of the chunk path."""
        _, ext = os.path.splitext(self.chunk_path)
        return ext.lower()

    @property
    def is_image(self) -> bool:
        """Whether this chunk is an image file."""
        return self.extension in IMAGE_EXTENSIONS


@dataclass(frozen=True)
class CompressionResult:
    """Result of compressing an image.

    Attributes:
        path: Output file path (original if no compression was needed).
        is_temp: ``True`` if *path* is a temp file that must be cleaned up.
    """

    path: str
    is_temp: bool


@dataclass
class BatchFileGroup:
    """All chunks originating from a single input file.

    Attributes:
        original_path: The caller-supplied file path.
        batch_index: Position in the original ``file_paths`` list.
        chunks: Ordered list of :class:`FileChunk` objects (usually 1, more if split).
    """

    original_path: str
    batch_index: int
    chunks: list[FileChunk] = field(default_factory=list)


@dataclass(frozen=True)
class DirectResult:
    """A file whose text was extracted directly (no OCR needed).

    Attributes:
        original_path: The caller-supplied file path.
        markdown: Extracted markdown content.
    """

    original_path: str
    markdown: Optional[str]


@dataclass
class PreparedBatch:
    """Result of the preparation phase.

    Separates files that need Mistral OCR from those that were resolved
    directly (e.g. oversized PPTX text extraction fallback).

    Attributes:
        file_groups: Groups of chunks to OCR via Mistral.
        direct_results: Files converted without Mistral (e.g. PPTX text fallback).
        failed_paths: Set of paths that failed during preparation.
    """

    file_groups: list[BatchFileGroup] = field(default_factory=list)
    direct_results: list[DirectResult] = field(default_factory=list)
    failed_paths: set[str] = field(default_factory=set)


# ======================================================================
# OCR result phase
# ======================================================================


@dataclass(frozen=True)
class OcrResult:
    """OCR result for a single chunk.

    Attributes:
        chunk: The chunk this result belongs to.
        markdown: Extracted markdown, or ``None`` if OCR failed.
        error: Error message if OCR failed.
    """

    chunk: FileChunk
    markdown: Optional[str]
    error: Optional[str] = None
