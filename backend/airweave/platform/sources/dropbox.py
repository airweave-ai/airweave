"""Dropbox source implementation."""

from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import DropboxAuthConfig
from airweave.platform.configs.config import DropboxConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.dropbox import (
    DropboxAccountEntity,
    DropboxFileEntity,
    DropboxFolderEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.storage import FileSkippedException
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Dropbox",
    short_name="dropbox",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    requires_byoc=True,
    auth_config_class=None,
    config_class=DropboxConfig,
    labels=["File Storage"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class DropboxSource(BaseSource):
    """Dropbox source connector integrates with the Dropbox API to extract and synchronize files.

    Connects to folder structures from your Dropbox account.

    It supports downloading and processing files.
    """

    @classmethod
    async def create(
        cls, access_token: Union[str, DropboxAuthConfig], config: Optional[Dict[str, Any]] = None
    ) -> "DropboxSource":
        """Create a new Dropbox source with credentials and config.

        Args:
            access_token: The OAuth access token for Dropbox API access
            config: Optional configuration parameters, like exclude_path

        Returns:
            A configured DropboxSource instance
        """
        instance = cls()

        token_value: Optional[str] = None
        if isinstance(access_token, DropboxAuthConfig):
            token_value = access_token.access_token
        elif isinstance(access_token, str):
            token_value = access_token

        if not token_value or not token_value.strip():
            raise ValueError("Dropbox access token is required")

        instance.access_token = token_value.strip()

        # Store config values as instance attributes
        if config:
            instance.exclude_path = config.get("exclude_path", "")
        else:
            instance.exclude_path = ""

        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _post_with_auth(
        self, client: httpx.AsyncClient, url: str, json_data: Dict = None
    ) -> Dict:
        """Make an authenticated POST request to the Dropbox API."""
        access_token = await self.get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}

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
            # Handle 401 Unauthorized - try refreshing token
            if e.response.status_code == 401 and self._token_manager:
                self.logger.debug("Received 401 error, attempting to refresh token")
                refreshed = await self._token_manager.refresh_on_unauthorized()

                if refreshed:
                    # Retry with new token (the retry decorator will handle this)
                    self.logger.debug("Token refreshed, retrying request")
                    raise  # Let tenacity retry with the refreshed token

            self.logger.error(f"HTTP Error in Dropbox API call: {e}")
            self.logger.error(f"Response body: {e.response.text}")
            raise

        except Exception as e:
            self.logger.error(f"Unexpected error in Dropbox API call: {e}")
            raise

    async def _generate_account_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
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
            display_name = name_data.get("display_name") or "Dropbox Account"
            account_id = account_data.get("account_id") or "dropbox-account"

            # Create and yield the account entity
            yield DropboxAccountEntity(
                account_id=account_id,
                display_name=display_name,
                breadcrumbs=[],
                abbreviated_name=name_data.get("abbreviated_name"),
                familiar_name=name_data.get("familiar_name"),
                given_name=name_data.get("given_name"),
                surname=name_data.get("surname"),
                email=account_data.get("email"),
                email_verified=account_data.get("email_verified", False),
                disabled=account_data.get("disabled", False),
                account_type=(
                    account_data.get("account_type", {}).get(".tag")
                    if account_data.get("account_type")
                    else None
                ),
                is_teammate=account_data.get("is_teammate", False),
                is_paired=account_data.get("is_paired", False),
                team_member_id=account_data.get("team_member_id"),
                locale=account_data.get("locale"),
                country=account_data.get("country"),
                profile_photo_url=account_data.get("profile_photo_url"),
                referral_link=account_data.get("referral_link"),
                space_used=account_data.get("space_usage", {}).get("used")
                if account_data.get("space_usage")
                else None,
                space_allocated=account_data.get("space_usage", {})
                .get("allocation", {})
                .get("allocated")
                if account_data.get("space_usage")
                else None,
                team_info=account_data.get("team"),
                root_info=account_data.get("root_info"),
            )

        except Exception as e:
            # Log error and yield a minimal fallback entity
            self.logger.error(f"Error fetching Dropbox account info: {str(e)}")
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
            id=folder_id if folder_id else f"folder-{folder_path}",
            breadcrumbs=[account_breadcrumb],
            name=folder_name,
            path_lower=entry.get("path_lower"),
            path_display=entry.get("path_display"),
            sharing_info=sharing_info,
            read_only=sharing_info.get("read_only", False),
            traverse_only=sharing_info.get("traverse_only", False),
            no_access=sharing_info.get("no_access", False),
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
            self.logger.error(f"Error fetching paginated entries from {url}: {str(e)}")
            raise

    async def _generate_folder_entities(
        self,
        client: httpx.AsyncClient,
        account_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[BaseEntity, None]:
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
                self.logger.error(f"Error listing Dropbox folder {current_path}: {str(e)}")
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

        # Determine file type from file name
        file_name = entry.get("name", "Unknown File")
        import mimetypes

        mime_type = mimetypes.guess_type(file_name)[0]
        if mime_type and "/" in mime_type:
            file_type = mime_type.split("/")[0]
        else:
            # Fallback to extension or generic file type
            import os

            ext = os.path.splitext(file_name)[1].lower().lstrip(".")
            file_type = ext if ext else "file"

        return DropboxFileEntity(
            id=file_id if file_id else f"file-{file_path}",
            breadcrumbs=folder_breadcrumbs,
            name=file_name,
            url="https://content.dropboxapi.com/2/files/download",
            size=entry.get("size", 0),
            file_type=file_type,
            mime_type=mime_type or "application/octet-stream",
            local_path=None,  # Will be set after download
            # API fields (Dropbox-specific)
            path_lower=entry.get("path_lower"),
            path_display=entry.get("path_display"),
            rev=entry.get("rev"),
            client_modified=client_modified,
            server_modified=server_modified,
            is_downloadable=entry.get("is_downloadable", True),
            content_hash=entry.get("content_hash"),
            sharing_info=sharing_info,
            has_explicit_shared_members=entry.get("has_explicit_shared_members"),
        )

    async def _generate_file_entities(
        self, client: httpx.AsyncClient, folder_breadcrumbs: List[Breadcrumb], folder_path: str = ""
    ) -> AsyncGenerator[BaseEntity, None]:
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
                        self.logger.debug(
                            f"Skipping non-downloadable file: "
                            f"{entry.get('path_display', 'unknown path')}"
                        )
                        continue

                    # Create file entity
                    file_entity = self._create_file_entity(entry, folder_breadcrumbs)

                    try:
                        # Download file using custom Dropbox download logic
                        # Dropbox requires POST with special header containing the file path
                        import json

                        dropbox_api_arg = json.dumps({"path": file_entity.path_lower})

                        async with self.http_client() as download_client:
                            access_token = await self.get_access_token()
                            headers = {
                                "Authorization": f"Bearer {access_token}",
                                "Dropbox-API-Arg": dropbox_api_arg,
                            }

                            # Dropbox uses POST for downloads
                            response = await download_client.post(
                                "https://content.dropboxapi.com/2/files/download",
                                headers=headers,
                            )
                            response.raise_for_status()

                            # Save the file content
                            content = response.content
                            await self.file_downloader.save_bytes(
                                entity=file_entity,
                                content=content,
                                filename_with_extension=file_entity.name,
                                logger=self.logger,
                            )

                            # Verify save succeeded
                            if not file_entity.local_path:
                                raise ValueError(
                                    f"Save failed - no local path set for {file_entity.name}"
                                )

                            self.logger.debug(f"Successfully downloaded file: {file_entity.name}")
                            yield file_entity

                    except FileSkippedException as e:
                        self.logger.debug(f"Skipping file: {e.reason}")
                        continue

                    except Exception as e:
                        self.logger.error(f"Failed to download file {file_entity.name}: {e}")
                        # Continue with other files even if one fails
                        continue

        except Exception as e:
            self.logger.error(f"Error listing files in Dropbox folder {folder_path}: {str(e)}")
            raise

    async def _process_folder_and_contents(
        self, client: httpx.AsyncClient, folder_path: str, folder_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[BaseEntity, None]:
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
                        entity_id=folder_entity.id,
                        name=folder_entity.name,
                        entity_type="DropboxFolderEntity",
                    )
                    # Build complete breadcrumb path to this folder
                    new_breadcrumbs = folder_breadcrumbs + [folder_breadcrumb]

                    # Recursively process this subfolder
                    async for entity in self._process_folder_and_contents(
                        client, subfolder_path, new_breadcrumbs
                    ):
                        yield entity

        except Exception as e:
            self.logger.error(f"Error processing folder {folder_path}: {str(e)}")
            raise

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Recursively generate all entities from Dropbox.

        Yields:
            A sequence of entities in the following order:
            1. Account-level entities
            2. For each folder (including root), folder entity and its contents recursively
        """
        async with self.http_client() as client:
            # 1. Account(s)
            async for account_entity in self._generate_account_entities(client):
                yield account_entity

                account_breadcrumb = Breadcrumb(
                    entity_id=account_entity.account_id,
                    name=account_entity.display_name,
                    entity_type="DropboxAccountEntity",
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
                    # Skip excluded paths
                    if (
                        self.exclude_path
                        and folder_entity.path_lower
                        and self.exclude_path in folder_entity.path_lower
                    ):
                        self.logger.debug(f"Skipping excluded folder: {folder_entity.path_lower}")
                        continue

                    yield folder_entity

                    folder_breadcrumb = Breadcrumb(
                        entity_id=folder_entity.id,
                        name=folder_entity.name,
                        entity_type="DropboxFolderEntity",
                    )
                    folder_breadcrumbs = [account_breadcrumb, folder_breadcrumb]

                    # Process all subfolders and their files recursively
                    async for entity in self._process_folder_and_contents(
                        client, folder_entity.path_lower, folder_breadcrumbs
                    ):
                        yield entity

    async def validate(self) -> bool:
        """Verify Dropbox OAuth2 token by calling /users/get_current_account (POST, no body)."""
        try:
            # Quick sanity check before making the request
            token = await self.get_access_token()
            if not token:
                self.logger.error("Dropbox validation failed: no access token available.")
                return False

            async with self.http_client(timeout=10.0) as client:
                # Uses the same auth/refresh/retry logic as the rest of the connector
                await self._post_with_auth(
                    client,
                    "https://api.dropboxapi.com/2/users/get_current_account",
                    None,  # no request body for this endpoint
                )
            return True

        except httpx.HTTPStatusError as e:
            self.logger.error(
                (
                    f"Dropbox validation failed: HTTP"
                    f"{e.response.status_code} - {e.response.text[:200]}"
                )
            )
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during Dropbox validation: {e}")
            return False
