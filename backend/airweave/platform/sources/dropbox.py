"""Dropbox source implementation."""

from typing import AsyncGenerator, Dict, List, Tuple

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.dropbox import (
    DropboxAccountEntity,
    DropboxFileEntity,
    DropboxFolderEntity,
)
from airweave.platform.sources._base import BaseSource


@source(
    "Dropbox",
    "dropbox",
    AuthType.oauth2_with_refresh,
    auth_config_class="DropboxAuthConfig",
    labels=["File Storage"],
)
class DropboxSource(BaseSource):
    """Dropbox source implementation."""

    @classmethod
    async def create(cls, access_token: str) -> "DropboxSource":
        """Create a new Dropbox source.

        Args:
            access_token: The OAuth2 access token for Dropbox API access.

        Returns:
            A configured DropboxSource instance.
        """
        instance = cls()
        instance.access_token = access_token
        return instance

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _post_with_auth(
        self, client: httpx.AsyncClient, url: str, json_data: Dict = None
    ) -> Dict:
        """Make an authenticated POST request to the Dropbox API."""
        headers = {"Authorization": f"Bearer {self.access_token}"}

        try:
            # Only include JSON data if it's provided
            if json_data is not None:
                response = await client.post(url, headers=headers, json=json_data)
            else:
                # Send a request with no body
                response = await client.post(url, headers=headers)
            response.raise_for_status()
            json_response = response.json()
            return json_response

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error in Dropbox API call: {e}")
            logger.error(f"Response body: {e.response.text}")
            raise

        except Exception as e:
            logger.error(f"Unexpected error in Dropbox API call: {e}")
            raise

    async def _generate_account_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate Dropbox account-level entities using the Dropbox API.

        Args:
            client: The HTTPX client instance.

        Yields:
            Account-level entities containing user information from Dropbox.
        """
        # Call the get_current_account endpoint to get account information
        url = "https://api.dropboxapi.com/2/users/get_current_account"

        try:
            # Get account details - pass None instead of {} to send no request body
            account_data = await self._post_with_auth(client, url, None)

            # Process name information
            name_data = account_data.get("name", {})

            # Create and yield the account entity
            yield DropboxAccountEntity(
                # Required ChunkEntity fields
                entity_id=account_data.get("account_id", "dropbox-account"),
                breadcrumbs=[],  # Top-level entity, no breadcrumbs
                # Core identification fields
                account_id=account_data.get("account_id"),
                # Name information
                name=name_data.get("display_name", "Dropbox Account"),
                abbreviated_name=name_data.get("abbreviated_name"),
                familiar_name=name_data.get("familiar_name"),
                given_name=name_data.get("given_name"),
                surname=name_data.get("surname"),
                # Account status and details
                email=account_data.get("email"),
                email_verified=account_data.get("email_verified", False),
                disabled=account_data.get("disabled", False),
                # Account type and relationships
                account_type=(
                    account_data.get("account_type", {}).get(".tag")
                    if account_data.get("account_type")
                    else None
                ),
                is_teammate=account_data.get("is_teammate", False),
                is_paired=account_data.get("is_paired", False),
                team_member_id=account_data.get("team_member_id"),
                # Regional and language settings
                locale=account_data.get("locale"),
                country=account_data.get("country"),
                # URLs and external references
                profile_photo_url=account_data.get("profile_photo_url"),
                referral_link=account_data.get("referral_link"),
                # Team information - keep whole object for reference
                team_info=account_data.get("team"),
                # Root information - keep whole object for reference
                root_info=account_data.get("root_info"),
            )

        except Exception as e:
            # Log error and yield a minimal fallback entity
            logger.error(f"Error fetching Dropbox account info: {str(e)}")
            raise

    def _create_folder_entity(
        self, entry: Dict, account_breadcrumb: Breadcrumb
    ) -> Tuple[DropboxFolderEntity, str]:
        """Create a DropboxFolderEntity from an API response entry.

        Args:
            entry: The folder entry from the Dropbox API
            account_breadcrumb: The breadcrumb for the parent account

        Returns:
            A tuple of (folder_entity, folder_path) for further processing
        """
        folder_id = entry.get("id", "")
        folder_name = entry.get("name", "Unnamed Folder")
        folder_path = entry.get("path_lower", "")

        # Extract sharing info safely
        sharing_info = entry.get("sharing_info", {})

        folder_entity = DropboxFolderEntity(
            # Required fields
            entity_id=folder_id if folder_id else f"folder-{folder_path}",
            breadcrumbs=[account_breadcrumb],
            folder_id=folder_id,
            name=folder_name,
            # Path information
            path_lower=entry.get("path_lower"),
            path_display=entry.get("path_display"),
            # Complete sharing info object
            sharing_info=sharing_info,
            # Key sharing fields extracted for convenience
            read_only=sharing_info.get("read_only", False),
            traverse_only=sharing_info.get("traverse_only", False),
            no_access=sharing_info.get("no_access", False),
            # Custom properties/tags
            property_groups=entry.get("property_groups"),
        )

        return folder_entity, folder_path

    async def _get_paginated_entries(
        self, client: httpx.AsyncClient, url: str, initial_data: Dict, continuation_url: str = None
    ) -> AsyncGenerator[Dict, None]:
        """Fetch all entries from a paginated Dropbox API endpoint.

        Args:
            client: The HTTPX client for making requests
            url: The initial API endpoint URL
            initial_data: The initial request payload
            continuation_url: URL for pagination continuation (if different from initial URL)

        Yields:
            Individual entries from the API responses, including all paginated results
        """
        if continuation_url is None:
            continuation_url = url

        try:
            # Make initial request
            response_data = await self._post_with_auth(client, url, initial_data)

            # Yield each entry from the initial response
            for entry in response_data.get("entries", []):
                yield entry

            # Continue fetching if there are more results
            while response_data.get("has_more", False):
                # Prepare continuation request
                continue_data = {"cursor": response_data.get("cursor")}

                # Make continuation request
                response_data = await self._post_with_auth(client, continuation_url, continue_data)

                # Yield each entry from the continuation response
                for entry in response_data.get("entries", []):
                    yield entry

        except Exception as e:
            logger.error(f"Error fetching paginated entries from {url}: {str(e)}")
            raise

    async def _generate_folder_entities(
        self,
        client: httpx.AsyncClient,
        account_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate folder entities for a given Dropbox account."""
        # Start with the root folder
        url = "https://api.dropboxapi.com/2/files/list_folder"
        continue_url = "https://api.dropboxapi.com/2/files/list_folder/continue"

        # Process all folders breadth-first
        folders_to_process = [("", "Root")]  # Start with root (path, name)

        while folders_to_process:
            current_path, current_name = folders_to_process.pop(0)

            # Configure to list the current folder
            data = {
                "path": current_path,
                "recursive": False,
                "include_deleted": False,
                "include_has_explicit_shared_members": True,
                "include_mounted_folders": True,
                "include_non_downloadable_files": True,
            }

            try:
                # Use our reusable pagination helper
                async for entry in self._get_paginated_entries(client, url, data, continue_url):
                    # Only process folders
                    if entry.get(".tag") == "folder":
                        # Create entity and get path for further processing
                        folder_entity, folder_path = self._create_folder_entity(
                            entry, account_breadcrumb
                        )
                        yield folder_entity

                        # Add this folder to be processed (for recursion)
                        folders_to_process.append((folder_path, folder_entity.name))

            except Exception as e:
                logger.error(f"Error listing Dropbox folder {current_path}: {str(e)}")
                raise

    def _create_file_entity(
        self, entry: Dict, folder_breadcrumbs: List[Breadcrumb]
    ) -> DropboxFileEntity:
        """Create a DropboxFileEntity from an API response entry.

        Args:
            entry: The file entry from the Dropbox API
            folder_breadcrumbs: List of breadcrumbs for the parent folders

        Returns:
            A DropboxFileEntity populated with data from the API
        """
        import json

        file_id = entry.get("id", "")
        file_path = entry.get("path_lower", "")

        # Parse timestamps if available
        client_modified = None
        server_modified = None

        if entry.get("client_modified"):
            try:
                from datetime import datetime

                client_modified = datetime.strptime(
                    entry.get("client_modified"), "%Y-%m-%dT%H:%M:%SZ"
                )
            except (ValueError, TypeError):
                pass

        if entry.get("server_modified"):
            try:
                from datetime import datetime

                server_modified = datetime.strptime(
                    entry.get("server_modified"), "%Y-%m-%dT%H:%M:%SZ"
                )
            except (ValueError, TypeError):
                pass

        # Extract sharing info
        sharing_info = entry.get("sharing_info", {})

        # Create custom headers that will be needed for Dropbox download
        # These will be stored in sync_metadata and used during file download
        dropbox_api_arg = json.dumps({"path": file_path})

        return DropboxFileEntity(
            # Required fields from ChunkEntity
            entity_id=file_id if file_id else f"file-{file_path}",
            breadcrumbs=folder_breadcrumbs,
            # Required fields from FileEntity
            file_id=file_id if file_id else f"file-{file_path}",
            name=entry.get("name", "Unknown File"),
            download_url="https://content.dropboxapi.com/2/files/download",
            # Store download headers as metadata
            sync_metadata={
                "headers": {"Dropbox-API-Arg": dropbox_api_arg},
                "method": "POST",  # Dropbox requires POST for download
            },
            # Optional fields from FileEntity
            mime_type=None,  # Not directly provided by Dropbox API
            size=entry.get("size"),
            # Dropbox-specific fields - ALL OPTIONAL
            path_lower=entry.get("path_lower"),
            path_display=entry.get("path_display"),
            rev=entry.get("rev"),
            client_modified=client_modified,
            server_modified=server_modified,
            is_downloadable=entry.get("is_downloadable", True),
            content_hash=entry.get("content_hash"),
            # Additional optional fields
            sharing_info=sharing_info,
            has_explicit_shared_members=entry.get("has_explicit_shared_members"),
        )

    async def _generate_file_entities(
        self, client: httpx.AsyncClient, folder_breadcrumbs: List[Breadcrumb], folder_path: str = ""
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate file entities within a given folder using the Dropbox API."""
        # Use list_folder API to get files in the folder
        url = "https://api.dropboxapi.com/2/files/list_folder"
        continue_url = "https://api.dropboxapi.com/2/files/list_folder/continue"

        data = {
            "path": folder_path,
            "recursive": False,
            "include_deleted": False,
            "include_has_explicit_shared_members": True,
            "include_mounted_folders": True,
            "include_non_downloadable_files": True,
        }

        try:
            # Use our reusable pagination helper
            async for entry in self._get_paginated_entries(client, url, data, continue_url):
                # Only process files (not folders)
                if entry.get(".tag") == "file":
                    # Skip non-downloadable files
                    if not entry.get("is_downloadable", True):
                        logger.info(
                            f"Skipping non-downloadable file: "
                            f"{entry.get('path_display', 'unknown path')}"
                        )
                        continue

                    # Create file entity with Dropbox-specific download metadata
                    file_entity = self._create_file_entity(entry, folder_breadcrumbs)

                    try:
                        # Use the BaseSource helper method instead of direct file_manager calls
                        processed_entity = await self.process_file_entity(
                            file_entity=file_entity,
                            access_token=self.access_token,
                            headers=file_entity.sync_metadata.get("headers"),
                        )

                        yield processed_entity

                    except Exception as e:
                        logger.error(f"Failed to process file {file_entity.name}: {str(e)}")
                        # Continue with other files even if one fails
                        continue

        except Exception as e:
            logger.error(f"Error listing files in Dropbox folder {folder_path}: {str(e)}")
            raise

    async def _process_folder_and_contents(
        self, client: httpx.AsyncClient, folder_path: str, folder_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process a folder recursively, yielding files and subfolders.

        Args:
            client: The HTTPX client for making requests
            folder_path: The path of the folder to process
            folder_breadcrumbs: List of breadcrumbs for navigating to this folder

        Yields:
            File entities for the current folder
            Folder entities for subfolders, followed by their contents
        """
        # First, yield all file entities in this folder
        async for file_entity in self._generate_file_entities(
            client, folder_breadcrumbs, folder_path
        ):
            yield file_entity

        # Then find and process all subfolders
        url = "https://api.dropboxapi.com/2/files/list_folder"
        continue_url = "https://api.dropboxapi.com/2/files/list_folder/continue"

        data = {
            "path": folder_path,
            "recursive": False,
            "include_deleted": False,
            "include_has_explicit_shared_members": True,
            "include_mounted_folders": True,
            "include_non_downloadable_files": True,
        }

        try:
            # Find all subfolders in the current folder
            async for entry in self._get_paginated_entries(client, url, data, continue_url):
                if entry.get(".tag") == "folder":
                    # Get account breadcrumb (always first in the list)
                    account_breadcrumb = folder_breadcrumbs[0] if folder_breadcrumbs else None

                    # Create folder entity
                    folder_entity, subfolder_path = self._create_folder_entity(
                        entry, account_breadcrumb
                    )
                    yield folder_entity

                    # Create new breadcrumb for this folder
                    folder_breadcrumb = Breadcrumb(
                        entity_id=folder_entity.folder_id,
                        name=folder_entity.name,
                        type="folder",
                    )
                    # Build complete breadcrumb path to this folder
                    new_breadcrumbs = folder_breadcrumbs + [folder_breadcrumb]

                    # Recursively process this subfolder
                    async for entity in self._process_folder_and_contents(
                        client, subfolder_path, new_breadcrumbs
                    ):
                        yield entity

        except Exception as e:
            logger.error(f"Error processing folder {folder_path}: {str(e)}")
            raise

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Recursively generate all entities from Dropbox.

        Yields:
            A sequence of entities in the following order:
            1. Account-level entities
            2. For each folder (including root), folder entity and its contents recursively
        """
        async with httpx.AsyncClient() as client:
            # 1. Account(s)
            async for account_entity in self._generate_account_entities(client):
                yield account_entity

                account_breadcrumb = Breadcrumb(
                    entity_id=account_entity.account_id,
                    name=account_entity.name,
                    type="account",
                )

                # Create breadcrumbs list with just the account
                account_breadcrumbs = [account_breadcrumb]

                # 2. Process root directory first (for files in root)
                async for file_entity in self._generate_file_entities(
                    client, account_breadcrumbs, ""
                ):
                    yield file_entity

                # 3. Process all folders recursively starting from root
                async for folder_entity in self._generate_folder_entities(
                    client, account_breadcrumb
                ):
                    yield folder_entity

                    folder_breadcrumb = Breadcrumb(
                        entity_id=folder_entity.folder_id,
                        name=folder_entity.name,
                        type="folder",
                    )
                    folder_breadcrumbs = [account_breadcrumb, folder_breadcrumb]

                    # Process all subfolders and their files recursively
                    async for entity in self._process_folder_and_contents(
                        client, folder_entity.path_lower, folder_breadcrumbs
                    ):
                        yield entity
