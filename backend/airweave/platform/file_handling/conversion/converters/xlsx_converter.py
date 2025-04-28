"""Excel to Markdown converter for XLSX files."""

from typing import Any, Union

import pandas as pd

from airweave.core.logging import logger
from airweave.platform.file_handling.conversion._base import (
    DocumentConverter,
    DocumentConverterResult,
)


class XlsxConverter(DocumentConverter):
    """Converts XLSX files to Markdown, with each sheet presented as a separate Markdown table."""

    async def convert(self, local_path: str, **kwargs: Any) -> Union[None, DocumentConverterResult]:
        """Convert an XLSX file to markdown.

        Args:
            local_path: Path to the XLSX file
            **kwargs: Additional arguments passed to converters

        Returns:
            DocumentConverterResult containing the markdown text
        """
        extension = kwargs.get("file_extension", "")
        if extension.lower() != ".xlsx":
            return None

        try:
            sheets = pd.read_excel(local_path, sheet_name=None)
            md_content = ""

            for sheet_name, df in sheets.items():
                md_content += f"## {sheet_name}\n"
                md_content += df.to_markdown(index=False) + "\n\n"

            return DocumentConverterResult(title=None, text_content=md_content.strip())
        except Exception as e:
            logger.error(f"Error converting XLSX file {local_path}: {str(e)}")
            return None
