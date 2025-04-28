"""PDF to Markdown converter with Mistral OCR support."""

import os
import tempfile
from typing import Any, Optional, Tuple, Union

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.platform.file_handling.conversion._base import (
    DocumentConverter,
    DocumentConverterResult,
)

# Initialize Mistral client if API key is available
mistral_client = None
if hasattr(settings, "MISTRAL_API_KEY") and settings.MISTRAL_API_KEY:
    from mistralai import Mistral

    mistral_client = Mistral(api_key=settings.MISTRAL_API_KEY)

# Maximum file size for Mistral OCR (50MB in bytes)
MAX_MISTRAL_FILE_SIZE = 50 * 1024 * 1024


class PdfConverter(DocumentConverter):
    """Converts PDF files to Markdown using Mistral OCR or falls back to PyPDF2."""

    def __init__(self):
        """Initialize the PDF converter with Mistral client if API key is available."""
        self.mistral_client = mistral_client

    async def convert(self, local_path: str, **kwargs: Any) -> Union[None, DocumentConverterResult]:
        """Convert a PDF file to markdown using Mistral OCR when available.

        Args:
            local_path: Path to the PDF file
            **kwargs: Additional arguments passed to converters

        Returns:
            AsyncDocumentConverterResult containing the markdown text
        """
        extension = kwargs.get("file_extension", "")
        if extension.lower() != ".pdf":
            return None

        # Try Mistral OCR first if available
        if self.mistral_client:
            try:
                md_content, title = await self._convert_with_mistral(local_path)
                return DocumentConverterResult(title=title, text_content=md_content)
            except Exception as e:
                logger.error(f"Error converting PDF with Mistral OCR: {str(e)}")
                logger.info("Falling back to PyPDF2")

        # Fall back to PyPDF2
        try:
            md_content, title = await self._convert_with_pypdf(local_path)
            return DocumentConverterResult(title=title, text_content=md_content)
        except ImportError:
            return DocumentConverterResult(
                title=None, text_content="PDF conversion requires Mistral API key or PyPDF2."
            )
        except Exception as e:
            logger.error(f"Error converting PDF with PyPDF2: {str(e)}")
            return None

    async def _convert_with_mistral(self, local_path: str) -> Tuple[str, Optional[str]]:
        """Convert PDF using Mistral OCR.

        Args:
            local_path: Path to the PDF file

        Returns:
            Tuple of (markdown_content, title)

        Raises:
            Exception: If Mistral OCR conversion fails
        """
        logger.info(f"Using Mistral OCR to process PDF: {local_path}")

        # Check file size
        file_size = os.path.getsize(local_path)
        if file_size > MAX_MISTRAL_FILE_SIZE:
            logger.info(
                f"PDF size ({file_size} bytes) exceeds Mistral's 50MB limit, splitting by page"
            )
            return await self._process_large_pdf(local_path)

        # Process normally for files under 50MB
        return await self._process_single_pdf(local_path)

    async def _process_single_pdf(self, pdf_path: str) -> Tuple[str, Optional[str]]:
        """Process a single PDF file with Mistral OCR.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Tuple of (markdown_content, title)
        """
        # Upload file to Mistral
        with open(pdf_path, "rb") as file:
            uploaded_pdf = self.mistral_client.files.upload(
                file={
                    "file_name": os.path.basename(pdf_path),
                    "content": file,
                },
                purpose="ocr",
            )

        # Get signed URL for accessing the file
        signed_url = self.mistral_client.files.get_signed_url(file_id=uploaded_pdf.id)

        # Process file with OCR
        ocr_response = self.mistral_client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "document_url",
                "document_url": signed_url.url,
            },
        )

        # Extract markdown content from each page
        md_content = ""
        for page in ocr_response.pages:
            md_content += f"{page.markdown}"

        # Try to extract title from metadata if available
        title = None
        if hasattr(ocr_response, "metadata") and ocr_response.metadata:
            if hasattr(ocr_response.metadata, "title"):
                title = ocr_response.metadata.title

        return md_content.strip(), title

    async def _process_large_pdf(self, pdf_path: str) -> Tuple[str, Optional[str]]:
        """Process a large PDF by splitting it into batches under 50MB and processing each batch.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Tuple of (markdown_content, title)
        """
        import PyPDF2

        title = None
        combined_md = ""
        temp_dir = tempfile.mkdtemp()

        try:
            # Open the PDF and get page count
            with open(pdf_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                title = self._extract_pdf_title(reader)

                # Calculate batch size
                num_pages, pages_per_batch = self._calculate_batch_size(pdf_path, reader)

                # Process in batches
                batch_num = 1
                for start_idx in range(0, num_pages, pages_per_batch):
                    end_idx = min(start_idx + pages_per_batch, num_pages)
                    batch_md = await self._process_page_batch(
                        reader, start_idx, end_idx, temp_dir, batch_num
                    )
                    combined_md += batch_md
                    batch_num += 1

            return combined_md.strip(), title

        finally:
            self._cleanup_temp_files(temp_dir)

    def _extract_pdf_title(self, reader) -> Optional[str]:
        """Extract title from PDF metadata if available."""
        if reader.metadata and hasattr(reader.metadata, "title"):
            return reader.metadata.title
        return None

    def _calculate_batch_size(self, pdf_path: str, reader) -> Tuple[int, int]:
        """Calculate number of pages and pages per batch."""
        num_pages = len(reader.pages)
        file_size = os.path.getsize(pdf_path)
        avg_page_size = file_size / num_pages if num_pages > 0 else 0

        # Calculate pages per batch to stay under 50MB limit (with 10% buffer)
        pages_per_batch = max(1, int((MAX_MISTRAL_FILE_SIZE * 0.9) / avg_page_size))

        logger.info(f"PDF has {num_pages} pages, avg {avg_page_size / 1024 / 1024:.2f}MB per page")
        logger.info(f"Processing in batches of {pages_per_batch} pages")

        return num_pages, pages_per_batch

    async def _process_page_batch(
        self, reader, start_idx: int, end_idx: int, temp_dir: str, batch_num: int
    ) -> str:
        """Process a batch of PDF pages."""
        from PyPDF2 import PdfWriter

        # Create batch PDF with multiple pages
        writer = PdfWriter()
        for i in range(start_idx, end_idx):
            writer.add_page(reader.pages[i])

        # Save the batch to a temporary file
        temp_batch_path = os.path.join(temp_dir, f"batch_{batch_num}.pdf")
        with open(temp_batch_path, "wb") as batch_file:
            writer.write(batch_file)

        # Check if the batch file is still under the limit
        batch_size = os.path.getsize(temp_batch_path)
        if batch_size > MAX_MISTRAL_FILE_SIZE:
            logger.warning(
                f"Batch {batch_num} size ({batch_size / 1024 / 1024:.2f}MB) exceeds limit"
            )
            # Process individual pages in this batch
            return await self._process_individual_pages(reader, start_idx, end_idx, temp_dir)
        else:
            # Process the batch
            try:
                batch_md, _ = await self._process_single_pdf(temp_batch_path)
                logger.info(f"Processed batch {batch_num} (pages {start_idx + 1}-{end_idx})")
                return batch_md + "\n\n"
            except Exception as e:
                logger.error(f"Error processing batch {batch_num}: {str(e)}")
                # Fall back to processing pages individually
                logger.info(
                    f"Falling back to processing pages {start_idx + 1}-{end_idx} individually"
                )
                return await self._process_individual_pages(reader, start_idx, end_idx, temp_dir)

    async def _process_individual_pages(
        self, reader, start_idx: int, end_idx: int, temp_dir: str
    ) -> str:
        """Process individual pages when batch processing fails."""
        from PyPDF2 import PdfWriter

        pages_md = ""
        num_pages = len(reader.pages)

        for i in range(start_idx, end_idx):
            single_writer = PdfWriter()
            single_writer.add_page(reader.pages[i])
            temp_page_path = os.path.join(temp_dir, f"page_{i + 1}.pdf")
            with open(temp_page_path, "wb") as page_file:
                single_writer.write(page_file)
            try:
                page_md, _ = await self._process_single_pdf(temp_page_path)
                pages_md += page_md + "\n\n"
                logger.info(f"Processed page {i + 1}/{num_pages}")
            except Exception as e:
                logger.error(f"Error processing page {i + 1}: {str(e)}")

        return pages_md

    def _cleanup_temp_files(self, temp_dir: str) -> None:
        """Clean up temporary files."""
        try:
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {str(e)}")

    async def _convert_with_pypdf(self, local_path: str) -> Tuple[str, Optional[str]]:
        """Convert PDF using PyPDF2 as fallback.

        Args:
            local_path: Path to the PDF file

        Returns:
            Tuple of (markdown_content, title)

        Raises:
            ImportError: If PyPDF2 is not installed
        """
        import PyPDF2

        md_content = ""
        title = None

        with open(local_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)

            # Try to extract title from metadata
            if reader.metadata and hasattr(reader.metadata, "title"):
                title = reader.metadata.title

            # Extract text from each page
            for _i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    md_content += f"{page_text}"

        return md_content.strip(), title
