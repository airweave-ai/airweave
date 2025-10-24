"""Base bongo class for Microsoft Graph API connectors.

Provides shared functionality for Monke tests of Microsoft Graph connectors:
- Authentication headers
- Rate limiting
- Filename sanitization
- Generic file cleanup patterns
"""

import asyncio
import time
from typing import Any, Dict, List

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger

GRAPH = "https://graph.microsoft.com/v1.0"


class MicrosoftGraphBongo(BaseBongo):
    """Base bongo for Microsoft Graph API connectors.

    Provides common functionality for testing Microsoft Office connectors:
    - PowerPoint
    - Word
    - Excel
    - OneNote
    - OneDrive
    """

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Microsoft Graph bongo.

        Args:
            credentials: Dict containing access_token
            **kwargs: Additional config (entity_count, openai_model, rate_limit_delay_ms)
        """
        super().__init__(credentials)
        self.access_token: str = credentials["access_token"]
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.rate_limit_delay = float(kwargs.get("rate_limit_delay_ms", 500)) / 1000.0
        self.logger = get_logger(self.__class__.__name__.lower().replace("bongo", "_bongo"))
        self._last_req = 0.0

    def _hdrs(self) -> Dict[str, str]:
        """Get standard headers for Graph API requests.

        Returns:
            Dict with Authorization and Content-Type headers
        """
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _pace(self):
        """Rate limiting helper to avoid hitting Graph API limits.

        Ensures minimum delay between requests based on rate_limit_delay.
        """
        now = time.time()
        if (delta := now - self._last_req) < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self._last_req = time.time()

    def _sanitize_filename(self, filename: str) -> str:
        r"""Sanitize filename by removing illegal characters for OneDrive.

        OneDrive doesn't allow these characters in filenames:
        \ / : * ? " < > |

        Also ensures filename length doesn't exceed limits.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename safe for OneDrive
        """
        # Replace illegal characters
        illegal_chars = ["\\", "/", ":", "*", "?", '"', "<", ">", "|"]
        safe_name = filename
        for char in illegal_chars:
            safe_name = safe_name.replace(char, "_")

        # Remove leading/trailing spaces and dots
        safe_name = safe_name.strip(". ")

        # Limit length to 200 characters (OneDrive has a 400 char limit for full path)
        if len(safe_name) > 200:
            # Keep the extension
            name, ext = (
                safe_name.rsplit(".", 1) if "." in safe_name else (safe_name, "")
            )
            safe_name = name[:195] + "." + ext if ext else name[:200]

        return safe_name

    async def _cleanup_orphaned_files(
        self,
        client: httpx.AsyncClient,
        stats: Dict[str, Any],
        file_prefix: str,
        file_extensions: List[str],
    ):
        """Generic cleanup for orphaned test files from previous runs.

        Searches OneDrive root for files matching the pattern and deletes them.

        Args:
            client: HTTP client for API requests
            stats: Stats dict to update (files_deleted, errors)
            file_prefix: File prefix to match (e.g., "Monke_")
            file_extensions: List of extensions to match (e.g., [".pptx", ".docx"])
        """
        try:
            await self._pace()
            r = await client.get("/me/drive/root/children", headers=self._hdrs())

            if r.status_code == 200:
                files = r.json().get("value", [])

                # Find test files matching pattern
                test_files = [
                    f
                    for f in files
                    if f.get("name", "").startswith(file_prefix)
                    and any(f.get("name", "").endswith(ext) for ext in file_extensions)
                ]

                if test_files:
                    self.logger.info(
                        f"🔍 Found {len(test_files)} orphaned test files"
                    )
                    for file in test_files:
                        try:
                            await self._pace()
                            del_r = await client.delete(
                                f"/me/drive/items/{file['id']}",
                                headers=self._hdrs(),
                            )
                            if del_r.status_code == 204:
                                stats["files_deleted"] = stats.get("files_deleted", 0) + 1
                                self.logger.info(
                                    f"✅ Deleted orphaned file: {file.get('name', 'Unknown')}"
                                )
                            else:
                                stats["errors"] = stats.get("errors", 0) + 1
                        except Exception as e:
                            stats["errors"] = stats.get("errors", 0) + 1
                            self.logger.warning(
                                f"⚠️  Failed to delete file {file['id']}: {e}"
                            )
        except Exception as e:
            self.logger.warning(f"⚠️  Could not search for orphaned files: {e}")

    async def _delete_with_retry(
        self,
        client: httpx.AsyncClient,
        item_id: str,
        item_name: str,
        max_retries: int = 3,
        initial_retry_delay: float = 2.0,
    ) -> bool:
        """Delete a file/item with retry logic for locked resources (423).

        Microsoft Graph API sometimes returns 423 when a file is being processed.
        This method implements exponential backoff retry logic.

        Args:
            client: HTTP client for API requests
            item_id: ID of the item to delete
            item_name: Name of the item (for logging)
            max_retries: Maximum number of retry attempts
            initial_retry_delay: Initial delay in seconds (doubles each retry)

        Returns:
            True if deletion succeeded, False otherwise
        """
        retry_delay = initial_retry_delay

        for attempt in range(max_retries):
            try:
                await self._pace()
                r = await client.delete(
                    f"/me/drive/items/{item_id}", headers=self._hdrs()
                )

                if r.status_code == 204:
                    return True

                elif r.status_code == 423 and attempt < max_retries - 1:
                    # Resource is locked, wait and retry
                    self.logger.warning(
                        "⏳ Resource locked (423), retrying in %ss (attempt %s/%s): %s",
                        retry_delay,
                        attempt + 1,
                        max_retries,
                        item_name,
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    # Other error or max retries reached
                    self.logger.warning(
                        f"Delete failed: {r.status_code} - {r.text[:200]}"
                    )
                    return False

            except Exception as e:
                self.logger.warning(f"Delete error for {item_name}: {e}")
                return False

        return False

