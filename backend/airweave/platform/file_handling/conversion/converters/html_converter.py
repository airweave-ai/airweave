"""HTML to Markdown converter."""

import re
import shutil
import subprocess
import tempfile
from typing import Any, Union

from airweave.core.logging import logger
from airweave.platform.file_handling.conversion._base import (
    DocumentConverter,
    DocumentConverterResult,
)


class HtmlConverter(DocumentConverter):
    """Converts HTML files to Markdown using html2text, pandoc, or BeautifulSoup as fallbacks."""

    async def convert(self, local_path: str, **kwargs: Any) -> Union[None, DocumentConverterResult]:
        """Convert an HTML file to markdown.

        Args:
            local_path: Path to the HTML file
            **kwargs: Additional arguments passed to converters

        Returns:
            DocumentConverterResult containing the markdown text
        """
        extension = kwargs.get("file_extension", "")
        if extension.lower() not in [".html", ".htm"]:
            return None

        md_content = ""
        title = None

        try:
            # Try using html2text
            import html2text

            with open(local_path, "r", encoding="utf-8") as file:
                html_content = file.read()

            # Try to extract title
            title_match = re.search(
                r"<title>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL
            )
            if title_match:
                title = title_match.group(1).strip()

            # Convert to markdown
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.ignore_tables = False
            md_content = h.handle(html_content)

        except ImportError:
            # Fall back to pandoc if html2text is not available
            try:
                if shutil.which("pandoc"):
                    with tempfile.NamedTemporaryFile(suffix=".md") as temp_file:
                        subprocess.run(
                            [
                                "pandoc",
                                local_path,
                                "-f",
                                "html",
                                "-t",
                                "markdown",
                                "-o",
                                temp_file.name,
                            ],
                            check=True,
                        )
                        with open(temp_file.name, "r") as f:
                            md_content = f.read()
                else:
                    # Simple fallback using BeautifulSoup
                    try:
                        from bs4 import BeautifulSoup

                        with open(local_path, "r", encoding="utf-8") as file:
                            soup = BeautifulSoup(file.read(), "html.parser")

                        # Try to extract title
                        if soup.title:
                            title = soup.title.string

                        # Extract text
                        md_content = soup.get_text()
                    except ImportError:
                        return DocumentConverterResult(
                            title=None,
                            text_content=(
                                "HTML conversion requires html2text, pandoc, or BeautifulSoup."
                            ),
                        )
            except Exception as e:
                logger.error(f"Error converting HTML with external tools: {str(e)}")
                return None

        return DocumentConverterResult(title=title, text_content=md_content.strip())
