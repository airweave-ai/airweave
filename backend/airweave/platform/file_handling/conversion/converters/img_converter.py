"""Image converter module for converting images to markdown.

This module provides functionality to convert images to markdown text
using Mistral OCR, metadata extraction, and optional LLM-based image description.
"""

import base64
import json
import mimetypes
import os
import shutil
import subprocess
from typing import Any, Dict, Optional, Union

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.platform.file_handling.conversion._base import (
    DocumentConverter,
    DocumentConverterResult,
)
from airweave.platform.sync.async_helpers import run_in_thread_pool

# Initialize Mistral client if API key is available
mistral_client = None
if hasattr(settings, "MISTRAL_API_KEY") and settings.MISTRAL_API_KEY:
    from mistralai import Mistral

    mistral_client = Mistral(api_key=settings.MISTRAL_API_KEY)

# Initialize OpenAI client if API key is available
openai_client = None
if hasattr(settings, "OPENAI_API_KEY") and settings.OPENAI_API_KEY:
    from openai import AsyncOpenAI

    openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Maximum file size for Mistral OCR (50MB in bytes)
MAX_MISTRAL_FILE_SIZE = 50 * 1024 * 1024


class AsyncImageConverter(DocumentConverter):
    """Converts images to markdown.

    Via Mistral OCRmetadata extraction and optional LLM description.
    """

    def __init__(self):
        """Initialize the image converter with available clients."""
        self.mistral_client = mistral_client
        self.openai_client = openai_client

        # Store the exiftool path instead of just a boolean
        self.exiftool_path = shutil.which("exiftool")
        self.exiftool_available = bool(self.exiftool_path)

        # Log available capabilities
        self._log_available_capabilities()

    def _log_available_capabilities(self):
        """Log which conversion capabilities are available."""
        capabilities = []
        if self.mistral_client:
            capabilities.append("Mistral OCR")
        if self.exiftool_available:
            capabilities.append("Exiftool metadata extraction")
        if self.openai_client:
            capabilities.append("OpenAI image description")

        if capabilities:
            logger.info(f"Image converter initialized with: {', '.join(capabilities)}")
        else:
            logger.warning("Image converter initialized without any processing capabilities")

    async def convert(self, local_path: str, **kwargs: Any) -> Union[None, DocumentConverterResult]:
        """Convert an image to markdown.

        Args:
            local_path: Path to the image file
            **kwargs: Additional arguments passed to converters

        Returns:
            AsyncDocumentConverterResult containing the markdown text
        """
        # Bail if not supported image type
        extension = kwargs.get("file_extension", "")
        if not self._is_supported_image(extension):
            return None

        # Check if we have minimum viable conversion capabilities
        if not self._has_minimum_viable_capabilities():
            logger.warning(
                f"Skipping image conversion for {local_path} due to insufficient capabilities"
            )
            return None

        md_content = ""

        # Try Mistral OCR first if available and file size is under 50MB
        ocr_result = await self._try_mistral_ocr(local_path)
        if ocr_result:
            return DocumentConverterResult(title=None, text_content=ocr_result.strip())

        # Add metadata if exiftool is available
        metadata_content = await self._extract_metadata_content(local_path)
        if metadata_content:
            md_content += metadata_content

        # Try describing the image with built-in OpenAI client
        llm_description = await self._try_llm_description(local_path, extension)
        if llm_description:
            md_content += f"\n# Description:\n{llm_description.strip()}\n"

        if not md_content.strip():
            logger.warning(f"No content extracted from image {local_path}")
            return None

        return DocumentConverterResult(title=None, text_content=md_content.strip())

    def _has_minimum_viable_capabilities(self) -> bool:
        """Check if we have enough capabilities for a meaningful conversion.

        Returns:
            True if we have at least one viable conversion method
        """
        return bool(self.mistral_client or self.exiftool_available or self.openai_client)

    def _is_supported_image(self, extension: str) -> bool:
        """Check if the file extension is supported.

        Args:
            extension: File extension including the dot

        Returns:
            True if supported, False otherwise
        """
        return extension.lower() in [".jpg", ".jpeg", ".png"]

    async def _try_mistral_ocr(self, local_path: str) -> Optional[str]:
        """Try to process the image with Mistral OCR if available.

        Args:
            local_path: Path to the image file

        Returns:
            OCR text result or None if unavailable or failed
        """
        if not self.mistral_client:
            return None

        try:
            file_size = os.path.getsize(local_path)
            if file_size <= MAX_MISTRAL_FILE_SIZE:
                ocr_text = await self._process_with_mistral_ocr(local_path)
                if ocr_text:
                    return ocr_text
            else:
                logger.warning(
                    f"Image {local_path} exceeds Mistral OCR size limit "
                    f"of {MAX_MISTRAL_FILE_SIZE / 1024 / 1024}MB"
                )
        except Exception as e:
            logger.error(f"Error processing image with Mistral OCR: {str(e)}")
            logger.info("Falling back to metadata extraction and LLM description")

        return None

    async def _extract_metadata_content(self, local_path: str) -> str:
        """Extract metadata from the image and format as markdown.

        Args:
            local_path: Path to the image file

        Returns:
            Formatted metadata content
        """
        if not self.exiftool_available:
            return ""

        md_content = ""
        metadata = await self._get_metadata(local_path)
        if metadata:
            for field in [
                "ImageSize",
                "Title",
                "Caption",
                "Description",
                "Keywords",
                "Artist",
                "Author",
                "DateTimeOriginal",
                "CreateDate",
                "GPSPosition",
            ]:
                if field in metadata:
                    md_content += f"{field}: {metadata[field]}\n"
        else:
            logger.info(f"No metadata extracted from {local_path}")

        return md_content

    async def _try_llm_description(self, local_path: str, extension: str) -> Optional[str]:
        """Try to get a description of the image using built-in OpenAI client.

        Args:
            local_path: Path to the image file
            extension: File extension

        Returns:
            Description text or None if unavailable
        """
        if not self.openai_client:
            return None

        try:
            prompt = "Write a detailed caption for this image."
            return await self._get_llm_description(local_path, extension, prompt)
        except Exception as e:
            logger.error(f"Error getting LLM description: {str(e)}")
            return None

    async def _process_with_mistral_ocr(self, image_path: str) -> str:
        """Process image using Mistral OCR.

        Args:
            image_path: Path to the image file

        Returns:
            String containing the OCR results in markdown format

        Raises:
            Exception: If Mistral OCR processing fails
        """
        logger.info(f"Using Mistral OCR to process image: {image_path}")

        # Upload file to Mistral (non-blocking)
        def _upload_file():
            with open(image_path, "rb") as file:
                return self.mistral_client.files.upload(
                    file={
                        "file_name": os.path.basename(image_path),
                        "content": file,
                    },
                    purpose="ocr",
                )

        uploaded_image = await run_in_thread_pool(_upload_file)

        # Get signed URL for accessing the file (non-blocking)
        signed_url = await run_in_thread_pool(
            self.mistral_client.files.get_signed_url, file_id=uploaded_image.id
        )

        # Process file with OCR (non-blocking)
        def _process_ocr():
            return self.mistral_client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "image_url",
                    "image_url": signed_url.url,
                },
            )

        ocr_response = await run_in_thread_pool(_process_ocr)

        # Extract markdown content from response
        md_content = ""

        # If there are pages in the response (like for multi-page images)
        if hasattr(ocr_response, "pages") and ocr_response.pages:
            for page in ocr_response.pages:
                md_content += f"{page.markdown}"
        # If it's a simple image with direct markdown content
        elif hasattr(ocr_response, "markdown"):
            md_content = ocr_response.markdown

        return md_content.strip()

    async def _get_metadata(self, local_path: str) -> Optional[Dict[str, Any]]:
        """Get image metadata using exiftool if available."""
        try:

            def _run_exiftool():
                result = subprocess.run(
                    [self.exiftool_path, "-json", local_path], capture_output=True, text=True
                )
                return result.stdout

            stdout = await run_in_thread_pool(_run_exiftool)
            return json.loads(stdout)[0]
        except Exception as e:
            logger.error(f"Error extracting metadata with exiftool: {str(e)}")
            return None

    async def _get_llm_description(self, local_path: str, extension: str, prompt: str) -> str:
        """Get image description from OpenAI.

        Args:
            local_path: Path to the image file
            extension: File extension
            prompt: Prompt for the image description

        Returns:
            Description text

        Raises:
            Exception: If OpenAI API call fails
        """
        # Convert image to data URI
        with open(local_path, "rb") as image_file:
            content_type, _ = mimetypes.guess_type("dummy" + extension)
            if not content_type:
                content_type = "image/jpeg"
            image_base64 = base64.b64encode(image_file.read()).decode("utf-8")
            data_uri = f"data:{content_type};base64,{image_base64}"

        # Prepare messages for LLM
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }
        ]

        # Get response from LLM (default to vision model)
        response = await self.openai_client.chat.completions.create(
            model="gpt-5-nano", messages=messages, max_completion_tokens=3000
        )
        return response.choices[0].message.content
