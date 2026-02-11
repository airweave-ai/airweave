"""Google Document AI OCR adapter.

Satisfies the :class:`~airweave.core.protocols.ocr.OcrProvider` protocol
using Google Cloud's Enterprise Document OCR processor.

The SDK is synchronous, so calls are wrapped in ``asyncio.to_thread()``
with bounded concurrency via a semaphore.

Auth wiring is deferred — the adapter accepts raw config at init.
Settings / infra integration will be added in a follow-up.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

from airweave.core.logging import logger

# Google Document AI online processing limit (20 MB).
MAX_FILE_SIZE_BYTES = 20_000_000

# Default concurrent OCR calls.
DEFAULT_CONCURRENCY = 5

# Extension → MIME type for Document AI.
_MIME_TYPES: Dict[str, str] = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".webp": "image/webp",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


class GoogleDocumentAIOcrAdapter:
    """Google Document AI OCR adapter.

    Wraps the ``google-cloud-documentai`` SDK behind the ``OcrProvider``
    protocol. Each file is sent to the online (synchronous) processing
    endpoint; results are the full extracted text.

    Usage::

        ocr = GoogleDocumentAIOcrAdapter(
            project_id="my-gcp-project",
            location="us",
            processor_id="abc123def456",
        )
        results = await ocr.convert_batch(["/tmp/doc.pdf"])
    """

    def __init__(
        self,
        project_id: str,
        location: str,
        processor_id: str,
        concurrency: int = DEFAULT_CONCURRENCY,
    ) -> None:
        """Initialize the adapter.

        Args:
            project_id: GCP project ID with Document AI API enabled.
            location: Processor region (``us`` or ``eu``).
            processor_id: ID of the Document AI OCR processor.
            concurrency: Max concurrent processing requests.
        """
        self._project_id = project_id
        self._location = location
        self._processor_id = processor_id
        self._concurrency = concurrency
        self._client: Any = None
        self._processor_name: Optional[str] = None

    # ------------------------------------------------------------------
    # Lazy client initialisation
    # ------------------------------------------------------------------

    def _ensure_client(self) -> None:
        """Create the Document AI client on first use."""
        if self._client is not None:
            return

        try:
            from google.api_core.client_options import ClientOptions
            from google.cloud import documentai
        except ImportError:
            raise RuntimeError(
                "google-cloud-documentai package required but not installed"
            )

        opts = ClientOptions(
            api_endpoint=f"{self._location}-documentai.googleapis.com"
        )
        self._client = documentai.DocumentProcessorServiceClient(
            client_options=opts
        )
        self._processor_name = self._client.processor_path(
            self._project_id, self._location, self._processor_id
        )
        logger.debug(
            f"Google Document AI client initialized "
            f"(processor={self._processor_name})"
        )

    # ------------------------------------------------------------------
    # OcrProvider protocol
    # ------------------------------------------------------------------

    async def convert_batch(
        self, file_paths: List[str]
    ) -> Dict[str, Optional[str]]:
        """Convert files to text via Google Document AI OCR.

        Args:
            file_paths: Local file paths to OCR.

        Returns:
            Mapping of ``file_path -> text`` (``None`` on per-file failure).
        """
        self._ensure_client()

        if not file_paths:
            return {}

        semaphore = asyncio.Semaphore(self._concurrency)
        results: Dict[str, Optional[str]] = {}

        async def _process_one(path: str) -> None:
            async with semaphore:
                results[path] = await self._ocr_single(path)

        await asyncio.gather(*[_process_one(p) for p in file_paths])
        return results

    # ------------------------------------------------------------------
    # Single file OCR
    # ------------------------------------------------------------------

    async def _ocr_single(self, path: str) -> Optional[str]:
        """OCR a single file via the online processing endpoint."""
        name = os.path.basename(path)

        # Check file size (20 MB online limit)
        try:
            file_size = os.path.getsize(path)
        except OSError as exc:
            logger.error(f"[GoogleDocAI] Cannot stat {name}: {exc}")
            return None

        if file_size > MAX_FILE_SIZE_BYTES:
            logger.warning(
                f"[GoogleDocAI] {name} is {file_size / 1_000_000:.1f}MB, "
                f"exceeds 20MB online limit — skipping"
            )
            return None

        # Determine MIME type
        _, ext = os.path.splitext(path)
        mime_type = _MIME_TYPES.get(ext.lower())
        if mime_type is None:
            logger.warning(f"[GoogleDocAI] Unsupported extension: {ext}")
            return None

        # Read file
        try:
            with open(path, "rb") as fh:
                content = fh.read()
        except OSError as exc:
            logger.error(f"[GoogleDocAI] Cannot read {name}: {exc}")
            return None

        # Call Document AI (sync SDK → thread)
        try:
            text = await asyncio.to_thread(
                self._process_document, content, mime_type
            )
        except Exception as exc:
            logger.error(f"[GoogleDocAI] OCR failed for {name}: {exc}")
            return None

        if not text or not text.strip():
            logger.warning(f"[GoogleDocAI] Empty text for {name}")
            return ""

        return text

    def _process_document(self, content: bytes, mime_type: str) -> str:
        """Synchronous Document AI call (runs in thread)."""
        from google.cloud import documentai

        raw_document = documentai.RawDocument(
            content=content, mime_type=mime_type
        )
        request = documentai.ProcessRequest(
            name=self._processor_name,
            raw_document=raw_document,
        )
        result = self._client.process_document(request=request)
        return result.document.text
