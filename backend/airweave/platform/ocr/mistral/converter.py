"""Mistral OCR provider.

This module ONLY handles OCR via Mistral. It does not do text extraction.
For PDFs, use :class:`PdfConverter` which orchestrates text extraction
with OCR fallback.

Implements the :class:`~airweave.core.protocols.ocr.OcrProvider` protocol.

Supported formats:
    * Documents: PDF, DOCX, PPTX
    * Images: JPG, JPEG, PNG

Oversized files (>50 MB) are handled per format:
    * PDF  -- split by pages (recursive halving), then OCR each chunk
    * DOCX -- split by paragraphs (recursive halving)
    * PPTX -- fallback to python-pptx text extraction (no OCR)
    * Images -- compressed via Pillow quality reduction
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import aiofiles.os

from airweave.core.logging import logger
from airweave.platform.converters.text_extractors.pptx import extract_pptx_text
from airweave.platform.ocr.mistral.compressor import compress_image
from airweave.platform.ocr.mistral.models import (
    IMAGE_EXTENSIONS,
    BatchFileGroup,
    DirectResult,
    FileChunk,
    OcrResult,
    PreparedBatch,
)
from airweave.platform.ocr.mistral.ocr_client import MistralOcrClient
from airweave.platform.ocr.mistral.splitters import (
    DocxSplitter,
    PdfSplitter,
    RecursiveSplitter,
)
from airweave.platform.sync.exceptions import EntityProcessingError, SyncFailureError

# Mistral upload limit.
MAX_FILE_SIZE_BYTES = 50_000_000  # 50 MB

# Reusable splitter instances (stateless).
_pdf_splitter = PdfSplitter()
_docx_splitter = DocxSplitter()


class MistralOCR:
    """Converts documents and images to markdown using Mistral OCR.

    Satisfies the :class:`~airweave.core.protocols.ocr.OcrProvider` protocol.

    This provider ONLY does OCR. It does not attempt text extraction.
    For hybrid text extraction + OCR, use :class:`PdfConverter` instead.

    Usage::

        ocr = MistralOCR()
        results = await ocr.convert_batch(["/tmp/doc.pdf", "/tmp/img.png"])
    """

    def __init__(self, concurrency: int = 10) -> None:
        """Initialize the converter.

        Args:
            concurrency: Maximum number of concurrent OCR calls.
        """
        self._client = MistralOcrClient(concurrency=concurrency)
        self._client.ensure_initialized()

    # ==================================================================
    # Public API (OcrProvider protocol)
    # ==================================================================

    async def convert_batch(self, file_paths: List[str]) -> Dict[str, Optional[str]]:
        """Convert files to markdown via Mistral OCR.

        Args:
            file_paths: Local file paths (PDF, DOCX, PPTX, JPG, JPEG, PNG).

        Returns:
            Mapping of ``file_path -> markdown`` (``None`` on per-file failure).
        """
        self._client.ensure_initialized()

        try:
            # 1. Prepare: split/compress oversized files
            prepared = await self._prepare(file_paths)

            # Short-circuit if nothing needs OCR
            all_chunks = self._flatten_chunks(prepared)
            if not all_chunks:
                logger.debug("No chunks need OCR after preparation")
                return self._build_final_results(prepared, [])

            # 2. OCR all chunks
            logger.debug(f"Starting OCR for {len(all_chunks)} chunks")
            ocr_results = await self._client.ocr_chunks(all_chunks)

            # 3. Reassemble per-file markdown
            final = self._build_final_results(prepared, ocr_results)

            # 4. Cleanup temp chunks (best effort)
            await self._cleanup_temp_chunks(prepared)

            return final

        except EntityProcessingError:
            raise
        except Exception as exc:
            error_msg = str(exc).lower()
            is_infra = any(
                kw in error_msg for kw in ("timeout", "api", "network", "connection", "rate limit")
            )
            if is_infra:
                logger.error(f"Mistral infrastructure failure: {exc}")
                raise SyncFailureError(f"Mistral infrastructure failure: {exc}")

            logger.error(f"Mistral OCR conversion failed: {exc}")
            raise SyncFailureError(f"Mistral OCR conversion failed: {exc}")

    # ==================================================================
    # Preparation
    # ==================================================================

    async def _prepare(self, file_paths: list[str]) -> PreparedBatch:
        """Inspect each file, split/compress as needed for OCR."""
        prepared = PreparedBatch()

        for batch_idx, path in enumerate(file_paths):
            try:
                await self._prepare_one(path, batch_idx, prepared)
            except EntityProcessingError as exc:
                logger.warning(f"Skipping file {os.path.basename(path)}: {exc}")
                prepared.failed_paths.add(path)
            except Exception as exc:
                logger.error(f"Unexpected error preparing {os.path.basename(path)}: {exc}")
                prepared.failed_paths.add(path)

        return prepared

    async def _prepare_one(self, path: str, batch_idx: int, prepared: PreparedBatch) -> None:
        """Prepare a single file for OCR."""
        stat = await aiofiles.os.stat(path)
        file_size = stat.st_size
        _, ext = os.path.splitext(path)
        ext = ext.lower()

        size_mb = file_size / 1_000_000
        name = os.path.basename(path)

        # --- Small enough to send as-is --------------------------------
        if file_size <= MAX_FILE_SIZE_BYTES:
            logger.debug(f"Document {name}: {size_mb:.1f}MB (OK)")
            group = BatchFileGroup(original_path=path, batch_index=batch_idx)
            group.chunks.append(
                FileChunk(
                    original_path=path,
                    chunk_path=path,
                    batch_index=batch_idx,
                    chunk_index=0,
                    is_temp=False,
                )
            )
            prepared.file_groups.append(group)
            return

        # --- Oversized -- dispatch by format ---------------------------
        logger.debug(f"Document {name} is {size_mb:.1f}MB, needs processing...")

        if ext in IMAGE_EXTENSIONS:
            await self._prepare_image(path, batch_idx, prepared)

        elif ext == ".pdf":
            await self._prepare_split(path, batch_idx, _pdf_splitter, prepared)

        elif ext == ".docx":
            await self._prepare_split(path, batch_idx, _docx_splitter, prepared)

        elif ext == ".pptx":
            await self._prepare_pptx_fallback(path, prepared)

        else:
            raise EntityProcessingError(f"Unsupported format: {ext}")

    async def _prepare_image(self, path: str, batch_idx: int, prepared: PreparedBatch) -> None:
        result = await compress_image(path, MAX_FILE_SIZE_BYTES)
        group = BatchFileGroup(original_path=path, batch_index=batch_idx)
        group.chunks.append(
            FileChunk(
                original_path=path,
                chunk_path=result.path,
                batch_index=batch_idx,
                chunk_index=0,
                is_temp=result.is_temp,
            )
        )
        prepared.file_groups.append(group)

    async def _prepare_split(
        self,
        path: str,
        batch_idx: int,
        splitter: RecursiveSplitter,
        prepared: PreparedBatch,
    ) -> None:
        chunk_paths = await splitter.split(path, MAX_FILE_SIZE_BYTES)

        if not chunk_paths:
            raise EntityProcessingError(
                f"Splitting produced no chunks for {os.path.basename(path)}"
            )

        group = BatchFileGroup(original_path=path, batch_index=batch_idx)
        for ci, cp in enumerate(chunk_paths):
            group.chunks.append(
                FileChunk(
                    original_path=path,
                    chunk_path=cp,
                    batch_index=batch_idx,
                    chunk_index=ci,
                    is_temp=(cp != path),
                )
            )
        prepared.file_groups.append(group)
        logger.debug(f"Split into {len(chunk_paths)} chunks")

    async def _prepare_pptx_fallback(self, path: str, prepared: PreparedBatch) -> None:
        """Extract text directly from an oversized PPTX (no OCR)."""
        logger.warning(
            f"PPTX {os.path.basename(path)} exceeds {MAX_FILE_SIZE_BYTES / 1_000_000:.0f}MB "
            f"limit -- falling back to text extraction (images/diagrams will be lost)"
        )
        markdown = await extract_pptx_text(path)
        prepared.direct_results.append(DirectResult(original_path=path, markdown=markdown))

    # ==================================================================
    # Reassembly
    # ==================================================================

    @staticmethod
    def _flatten_chunks(prepared: PreparedBatch) -> list[FileChunk]:
        """Collect all chunks across file groups into a flat list."""
        return [chunk for group in prepared.file_groups for chunk in group.chunks]

    @staticmethod
    def _resolve_chunk(
        chunk: FileChunk,
        ocr_by_key: dict[tuple[int, int], OcrResult],
        file_name: str,
    ) -> Optional[str]:
        """Resolve a single chunk's OCR result to markdown.

        Args:
            chunk: The chunk to resolve.
            ocr_by_key: Lookup of (batch_index, chunk_index) -> OcrResult.
            file_name: Display name for log messages.

        Returns:
            Markdown string, or ``None`` if OCR failed for this chunk.
        """
        key = (chunk.batch_index, chunk.chunk_index)
        result = ocr_by_key.get(key)

        if result is None:
            logger.error(f"Conversion failed for {file_name}: chunk not processed")
            return None

        if result.markdown is None:
            error_info = f" ({result.error})" if result.error else ""
            logger.error(f"Conversion failed for {file_name}: OCR failed{error_info}")
            return None

        if not result.markdown.strip():
            logger.warning(f"OCR returned empty markdown for {file_name}")

        return result.markdown

    @staticmethod
    def _assemble_group(
        group: BatchFileGroup,
        ocr_by_key: dict[tuple[int, int], OcrResult],
    ) -> Optional[str]:
        """Assemble markdown for all chunks in a file group.

        Args:
            group: The file group whose chunks should be assembled.
            ocr_by_key: Lookup of (batch_index, chunk_index) -> OcrResult.

        Returns:
            Combined markdown string, or ``None`` if any chunk failed.
        """
        name = os.path.basename(group.original_path)
        parts = [MistralOCR._resolve_chunk(chunk, ocr_by_key, name) for chunk in group.chunks]

        if any(p is None for p in parts):
            return None
        if len(parts) == 1:
            return parts[0]
        return "\n\n---\n\n".join(parts)  # type: ignore[arg-type]

    @staticmethod
    def _build_final_results(
        prepared: PreparedBatch,
        ocr_results: list[OcrResult],
    ) -> dict[str, Optional[str]]:
        """Merge OCR results with direct results and failures."""
        ocr_by_key: dict[tuple[int, int], OcrResult] = {
            (r.chunk.batch_index, r.chunk.chunk_index): r for r in ocr_results
        }

        final: dict[str, Optional[str]] = {}

        for group in prepared.file_groups:
            final[group.original_path] = MistralOCR._assemble_group(group, ocr_by_key)

        for dr in prepared.direct_results:
            final[dr.original_path] = dr.markdown

        for path in prepared.failed_paths:
            if path not in final:
                logger.error(f"Conversion failed for {os.path.basename(path)}")
                final[path] = None

        return final

    # ==================================================================
    # Cleanup
    # ==================================================================

    async def _cleanup_temp_chunks(self, prepared: PreparedBatch) -> None:
        """Best-effort cleanup of temporary chunk files."""
        for group in prepared.file_groups:
            for chunk in group.chunks:
                if chunk.is_temp:
                    try:
                        await aiofiles.os.remove(chunk.chunk_path)
                    except Exception:
                        pass
