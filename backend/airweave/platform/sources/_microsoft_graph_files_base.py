"""Base class for file-based Microsoft Graph API connectors.

Provides shared functionality for connectors that work with OneDrive/SharePoint files:
- Recursive file discovery in folder hierarchies
- Generic file filtering by extension
- Pagination handling
- Folder depth limiting
"""

from typing import Any, AsyncGenerator, Dict, Optional, Tuple

import httpx

from airweave.platform.sources._microsoft_graph_base import MicrosoftGraphSource


class MicrosoftGraphFilesSource(MicrosoftGraphSource):
    """Base class for file-based Microsoft Graph API connectors.

    Designed for connectors that sync files from OneDrive/SharePoint:
    - PowerPoint (.pptx, .ppt, etc.)
    - Word (.docx, .doc, etc.)
    - Excel (.xlsx, .xls, etc.)
    - Generic file connectors (OneDrive, SharePoint)

    Subclasses just need to:
    1. Set FILE_EXTENSIONS tuple
    2. Implement generate_entities() to process discovered files
    """

    # Configuration constants - subclasses can override
    PAGE_SIZE_DRIVE = 250  # Optimal page size for drive items
    MAX_FOLDER_DEPTH = 5  # Limit recursive folder traversal depth

    # Subclasses must override this with their file extensions
    FILE_EXTENSIONS: Tuple[str, ...] = ()

    async def _discover_files_recursive(
        self,
        client: httpx.AsyncClient,
        folder_id: Optional[str] = None,
        depth: int = 0,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Recursively discover files in OneDrive/SharePoint folders.

        This is a generic file discovery method that works for any file type.
        It filters files based on the FILE_EXTENSIONS tuple defined by subclasses.

        Features:
        - Recursive folder traversal with depth limiting
        - Pagination support
        - Automatic filtering by file extension
        - Error recovery (skips problematic folders)

        Args:
            client: HTTP client for API requests
            folder_id: ID of folder to search (None for root)
            depth: Current recursion depth (used for depth limiting)

        Yields:
            DriveItem dictionaries for files matching FILE_EXTENSIONS
        """
        # Check depth limit
        if depth > self.MAX_FOLDER_DEPTH:
            self.logger.debug(
                f"Max folder depth {self.MAX_FOLDER_DEPTH} reached, skipping deeper traversal"
            )
            return

        # Build URL for folder or root
        if folder_id:
            url = f"{self.GRAPH_BASE_URL}/me/drive/items/{folder_id}/children"
        else:
            url = f"{self.GRAPH_BASE_URL}/me/drive/root/children"

        params = {"$top": self.PAGE_SIZE_DRIVE}

        try:
            # Process all pages in this folder
            while url:
                data = await self._get_with_auth(client, url, params=params)
                items = data.get("value", [])

                # Separate files and folders for processing
                folders_to_traverse = []

                for item in items:
                    file_name = item.get("name", "")

                    # Check if it matches our file extensions
                    if file_name.lower().endswith(self.FILE_EXTENSIONS):
                        yield item

                    # Collect folders for recursive traversal
                    elif "folder" in item:
                        folders_to_traverse.append(item.get("id"))

                # Recursively process subfolders
                for subfolder_id in folders_to_traverse:
                    async for file in self._discover_files_recursive(
                        client, subfolder_id, depth + 1
                    ):
                        yield file

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    params = None  # nextLink includes params

        except Exception as e:
            self.logger.warning(f"Error discovering files in folder (depth={depth}): {str(e)}")
            # Continue with other folders even if this one fails
