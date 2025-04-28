"""Text file to Markdown converter."""

import csv
import json
import xml.dom.minidom
from typing import Any, Union

from airweave.core.logging import logger
from airweave.platform.file_handling.conversion._base import (
    DocumentConverter,
    DocumentConverterResult,
)


class TextConverter(DocumentConverter):
    """Converts plain text files (TXT, CSV, JSON, XML) to Markdown."""

    async def convert(self, local_path: str, **kwargs: Any) -> Union[None, DocumentConverterResult]:
        """Convert a text file to markdown.

        Args:
            local_path: Path to the text file
            **kwargs: Additional arguments passed to converters

        Returns:
            DocumentConverterResult containing the markdown text
        """
        extension = kwargs.get("file_extension", "")
        if extension.lower() not in [".txt", ".csv", ".json", ".xml"]:
            return None

        md_content = ""
        title = None

        try:
            # For CSV files, convert to markdown table
            if extension.lower() == ".csv":
                try:
                    md_content = await self._convert_csv_to_markdown(local_path)
                except Exception as e:
                    logger.error(f"Error converting CSV to markdown table: {str(e)}")
                    # Fallback to raw content
                    with open(local_path, "r", encoding="utf-8") as file:
                        md_content = file.read()

            # For JSON files, pretty print
            elif extension.lower() == ".json":
                try:
                    with open(local_path, "r", encoding="utf-8") as file:
                        content = file.read()
                    md_content = await self._convert_json_to_markdown(content)
                except Exception as e:
                    logger.error(f"Error formatting JSON: {str(e)}")
                    # Fallback to raw content
                    with open(local_path, "r", encoding="utf-8") as file:
                        content = file.read()
                    md_content = "```\n" + content + "\n```"

            # For XML files, pretty print
            elif extension.lower() == ".xml":
                try:
                    with open(local_path, "r", encoding="utf-8") as file:
                        content = file.read()
                    md_content = await self._convert_xml_to_markdown(content)
                except Exception as e:
                    logger.error(f"Error formatting XML: {str(e)}")
                    # Fallback to raw content
                    with open(local_path, "r", encoding="utf-8") as file:
                        content = file.read()
                    md_content = "```\n" + content + "\n```"

            # For plain text, just use the content
            else:
                with open(local_path, "r", encoding="utf-8") as file:
                    md_content = file.read()

            return DocumentConverterResult(title=title, text_content=md_content.strip())
        except Exception as e:
            logger.error(f"Error reading text file: {str(e)}")
            return None

    async def _convert_csv_to_markdown(self, local_path: str) -> str:
        """Convert CSV file to markdown table.

        Args:
            local_path: Path to the CSV file

        Returns:
            Markdown table content
        """
        md_content = ""
        csv_data = []

        with open(local_path, "r", encoding="utf-8") as csv_file:
            csv_reader = csv.reader(csv_file)
            for row in csv_reader:
                csv_data.append(row)

        if csv_data:
            # Create header
            md_content += "| " + " | ".join(csv_data[0]) + " |\n"
            md_content += "|" + "|".join(["---" for _ in csv_data[0]]) + "|\n"

            # Add data rows
            for row in csv_data[1:]:
                md_content += "| " + " | ".join(row) + " |\n"

        return md_content

    async def _convert_json_to_markdown(self, content: str) -> str:
        """Convert JSON content to formatted markdown.

        Args:
            content: JSON content as string

        Returns:
            Formatted markdown content
        """
        parsed_json = json.loads(content)
        return "```json\n" + json.dumps(parsed_json, indent=2) + "\n```"

    async def _convert_xml_to_markdown(self, content: str) -> str:
        """Convert XML content to formatted markdown.

        Args:
            content: XML content as string

        Returns:
            Formatted markdown content
        """
        parsed_xml = xml.dom.minidom.parseString(content)
        return "```xml\n" + parsed_xml.toprettyxml() + "\n```"
