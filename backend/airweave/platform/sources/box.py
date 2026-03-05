"""Box source implementation for syncing folders, files, comments, users, and collaborations."""

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.exceptions import TokenRefreshError
from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import BoxAuthConfig
from airweave.platform.configs.config import BoxConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.box import (
    BoxCollaborationEntity,
    BoxCommentEntity,
    BoxFileEntity,
    BoxFolderEntity,
    BoxUserEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.storage import FileSkippedException
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Box",
    short_name="box",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    auth_config_class=BoxAuthConfig,
    config_class=BoxConfig,
    labels=["Storage"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class BoxSource(BaseSource):
    """Box source connector integrates with the Box API to extract and synchronize data.

    Connects to your Box account and syncs folders, files, comments, users, and collaborations.
    """

    API_BASE = "https://api.box.com/2.0"

    # Box API rate limit: 1000 requests/minute per user
    # We use 100ms delay = 600 requests/minute to stay comfortably under the limit
    MIN_REQUEST_DELAY = 0.1  # 100ms between requests

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "BoxSource":
        """Create a new Box source.

        Args:
            access_token: OAuth access token for Box API
            config: Optional configuration parameters

        Returns:
            Configured BoxSource instance
        """
        instance = cls()
        instance.access_token = access_token

        # Store config values as instance attributes
        # folder_id defaults to "0" (root) if not provided or empty
        folder_id = "0"
        if config:
            config_folder_id = config.get("folder_id", "0")
            # Handle empty string or None - use default "0"
            if config_folder_id and str(config_folder_id).strip():
                folder_id = str(config_folder_id).strip()

        instance.folder_id = folder_id

        # Rate limiting state
        instance.last_request_time = 0.0

        return instance

    async def _rate_limit(self):
        """Simple rate limiting to respect Box API limits.

        Box allows 1000 requests/minute per user. We use 100ms delay between
        requests (600 req/min) to stay comfortably under the limit.
        """
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.MIN_REQUEST_DELAY:
            await asyncio.sleep(self.MIN_REQUEST_DELAY - elapsed)
        self.last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """Make authenticated GET request to Box API with token refresh support.

        Retries on:
        - 429 rate limits (respects Retry-After header)
        - Timeout errors (exponential backoff)

        Args:
            client: HTTP client to use for the request
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response from the API

        Raises:
            TokenRefreshError: If token refresh fails
            httpx.HTTPStatusError: For other HTTP errors
        """
        # Rate limit to respect Box API limits (1000 req/min)
        await self._rate_limit()

        # Get a valid token (will refresh if needed)
        access_token = await self.get_access_token()
        if not access_token:
            raise ValueError("No access token available")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            response = await client.get(url, headers=headers, params=params)

            # Handle 401 Unauthorized - token might have expired
            if response.status_code == 401:
                self.logger.warning(f"Received 401 Unauthorized for {url}, refreshing token...")

                # If we have a token manager, try to refresh
                if self.token_manager:
                    try:
                        # Force refresh the token
                        new_token = await self.token_manager.refresh_on_unauthorized()
                        headers = {
                            "Authorization": f"Bearer {new_token}",
                            "Accept": "application/json",
                        }

                        # Retry the request with the new token
                        self.logger.debug(f"Retrying request with refreshed token: {url}")
                        response = await client.get(url, headers=headers, params=params)

                    except TokenRefreshError as e:
                        self.logger.error(f"Failed to refresh token: {str(e)}")
                        response.raise_for_status()
                else:
                    # No token manager, can't refresh
                    self.logger.error("No token manager available to refresh expired token")
                    response.raise_for_status()

            # Handle 404 Not Found - item might have been deleted
            if response.status_code == 404:
                self.logger.warning(f"Item not found (404): {url}")
                return {}

            # Handle 403 Forbidden - no access
            if response.status_code == 403:
                self.logger.warning(f"Access forbidden (403): {url}")
                return {}

            # Raise for other HTTP errors
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from Box API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Box API: {url}, {str(e)}")
            raise

    async def _get_current_user(self, client: httpx.AsyncClient) -> Optional[Dict]:
        """Get information about the current authenticated user.

        Args:
            client: HTTP client to use

        Returns:
            User information dictionary or None if failed
        """
        try:
            user_data = await self._get_with_auth(client, f"{self.API_BASE}/users/me")
            return user_data
        except Exception as e:
            self.logger.error(f"Failed to get current user: {e}")
            return None

    async def _generate_user_entity(
        self, client: httpx.AsyncClient, user_id: str
    ) -> Optional[BoxUserEntity]:
        """Generate a user entity for a given user ID.

        Args:
            client: HTTP client to use
            user_id: Box user ID

        Returns:
            BoxUserEntity or None if failed
        """
        try:
            user_data = await self._get_with_auth(client, f"{self.API_BASE}/users/{user_id}")

            if not user_data:
                return None

            return BoxUserEntity(
                user_id=user_data["id"],
                breadcrumbs=[],
                name=user_data.get("name", user_data.get("login", "")),
                created_at=user_data.get("created_at"),
                updated_at=user_data.get("modified_at"),
                login=user_data.get("login"),
                status=user_data.get("status"),
                job_title=user_data.get("job_title"),
                phone=user_data.get("phone"),
                address=user_data.get("address"),
                language=user_data.get("language"),
                timezone=user_data.get("timezone"),
                space_amount=user_data.get("space_amount"),
                space_used=user_data.get("space_used"),
                max_upload_size=user_data.get("max_upload_size"),
                avatar_url=user_data.get("avatar_url"),
            )
        except Exception as e:
            self.logger.debug(f"Failed to get user {user_id}: {e}")
            return None

    def _create_folder_entity(
        self, folder_data: Dict, breadcrumbs: List[Breadcrumb]
    ) -> BoxFolderEntity:
        """Create a BoxFolderEntity from API response data.

        Args:
            folder_data: Folder data from Box API
            breadcrumbs: Parent breadcrumbs

        Returns:
            BoxFolderEntity instance
        """
        # Safely extract parent information (None for root folder)
        parent = folder_data.get("parent") or {}
        parent_id = parent.get("id") if parent else None
        parent_name = parent.get("name") if parent else None

        # Safely extract path collection
        path_collection_data = folder_data.get("path_collection") or {}
        path_entries = path_collection_data.get("entries") or []

        return BoxFolderEntity(
            folder_id=folder_data["id"],
            breadcrumbs=breadcrumbs,
            name=folder_data.get("name", ""),
            created_at=folder_data.get("created_at"),
            updated_at=folder_data.get("modified_at"),
            description=folder_data.get("description"),
            size=folder_data.get("size"),
            path_collection=[
                {"id": entry.get("id"), "name": entry.get("name")} for entry in path_entries
            ],
            content_created_at=folder_data.get("content_created_at"),
            content_modified_at=folder_data.get("content_modified_at"),
            created_by=folder_data.get("created_by"),
            modified_by=folder_data.get("modified_by"),
            owned_by=folder_data.get("owned_by"),
            parent_id=parent_id,
            parent_name=parent_name,
            item_status=folder_data.get("item_status"),
            shared_link=folder_data.get("shared_link"),
            folder_upload_email=folder_data.get("folder_upload_email"),
            tags=folder_data.get("tags", []),
            has_collaborations=folder_data.get("has_collaborations"),
            permissions=folder_data.get("permissions"),
            permalink_url=f"https://app.box.com/folder/{folder_data['id']}",
            etag=folder_data.get("etag"),
            sequence_id=folder_data.get("sequence_id"),
        )

    async def _process_folder_items(
        self, client: httpx.AsyncClient, folder_id: str, folder_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process all items (files and subfolders) within a folder with pagination.

        Args:
            client: HTTP client to use
            folder_id: Box folder ID
            folder_breadcrumbs: Breadcrumbs including current folder

        Yields:
            BaseEntity instances for all items in the folder
        """
        offset = 0
        limit = 1000
        item_fields = (
            "id,name,type,description,size,path_collection,created_at,modified_at,"
            "content_created_at,content_modified_at,created_by,modified_by,owned_by,"
            "parent,item_status,shared_link,tags,has_collaborations,permissions,"
            "etag,sequence_id,sha1,extension,version_number,comment_count,lock"
        )

        while True:
            items_data = await self._get_with_auth(
                client,
                f"{self.API_BASE}/folders/{folder_id}/items",
                params={"fields": item_fields, "limit": limit, "offset": offset},
            )

            if not items_data or not items_data.get("entries"):
                break

            for item in items_data.get("entries", []):
                item_type = item.get("type")

                # Skip trashed items (deleted but still returned by API)
                if item.get("item_status") == "trashed":
                    self.logger.debug(f"Skipping trashed {item_type}: {item.get('name')}")
                    continue

                if item_type == "folder":
                    # Recursively process subfolder
                    async for entity in self._generate_folder_entities(
                        client, item["id"], folder_breadcrumbs
                    ):
                        yield entity

                elif item_type == "file":
                    # Process file
                    async for entity in self._generate_file_entities(
                        client, item, folder_breadcrumbs
                    ):
                        yield entity

            # Check for more items
            total_count = items_data.get("total_count", 0)
            offset += limit
            if offset >= total_count:
                break

    async def _generate_folder_entities(
        self, client: httpx.AsyncClient, folder_id: str, breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate folder and file entities recursively for a folder.

        Args:
            client: HTTP client to use
            folder_id: Box folder ID to sync
            breadcrumbs: Parent breadcrumbs for this folder

        Yields:
            BaseEntity instances for folders, files, comments, and collaborations
        """
        # Get folder details
        folder_fields = (
            "id,name,description,size,path_collection,created_at,modified_at,"
            "content_created_at,content_modified_at,created_by,modified_by,"
            "owned_by,parent,item_status,shared_link,folder_upload_email,"
            "tags,has_collaborations,permissions,etag,sequence_id"
        )
        folder_data = await self._get_with_auth(
            client,
            f"{self.API_BASE}/folders/{folder_id}",
            params={"fields": folder_fields},
        )

        if not folder_data:
            return

        # Create and yield folder entity
        folder_entity = self._create_folder_entity(folder_data, breadcrumbs)
        yield folder_entity

        folder_breadcrumb = Breadcrumb(
            entity_id=folder_entity.folder_id,
            name=folder_entity.name,
            entity_type="BoxFolderEntity",
        )
        folder_breadcrumbs = [*breadcrumbs, folder_breadcrumb]

        # Generate collaborations for this folder (skip root folder - ID 0)
        # Box API doesn't support collaborations on the root folder
        if folder_data["id"] != "0":
            async for collab_entity in self._generate_collaboration_entities(
                client, folder_data["id"], "folder", folder_data.get("name", ""), folder_breadcrumbs
            ):
                yield collab_entity

        # Process all items in this folder (files and subfolders)
        async for entity in self._process_folder_items(client, folder_id, folder_breadcrumbs):
            yield entity

    async def _generate_file_entities(
        self, client: httpx.AsyncClient, file_data: Dict, breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate file entity and related entities (comments, collaborations).

        Args:
            client: HTTP client to use
            file_data: File data from Box API
            breadcrumbs: Parent breadcrumbs

        Yields:
            File, comment, and collaboration entities
        """
        # Safely extract parent and path information
        parent = file_data.get("parent") or {}
        parent_folder_id = parent.get("id") if parent else ""
        parent_folder_name = parent.get("name") if parent else ""

        path_collection_data = file_data.get("path_collection") or {}
        path_entries = path_collection_data.get("entries") or []

        file_name = file_data.get("name", "")
        file_extension = file_data.get("extension", "").lower()
        mime_type = file_data.get("mime_type") or "application/octet-stream"
        size = file_data.get("size", 0)

        # Check if this is a Box Note (proprietary format that can't be downloaded)
        is_box_note = file_extension == "boxnote"

        # Determine file type from mime_type or extension
        if mime_type and "/" in mime_type:
            file_type = mime_type.split("/")[0]
        elif file_extension:
            file_type = file_extension
        else:
            file_type = "file"

        file_entity = BoxFileEntity(
            file_id=file_data["id"],
            breadcrumbs=breadcrumbs,
            name=file_name,
            created_at=file_data.get("created_at"),
            updated_at=file_data.get("modified_at"),
            url=f"{self.API_BASE}/files/{file_data['id']}/content",
            size=size,
            file_type=file_type,
            mime_type=mime_type,
            local_path=None,
            description=file_data.get("description"),
            parent_folder_id=parent_folder_id,
            parent_folder_name=parent_folder_name,
            path_collection=[
                {"id": entry.get("id"), "name": entry.get("name")} for entry in path_entries
            ],
            sha1=file_data.get("sha1"),
            extension=file_data.get("extension"),
            version_number=file_data.get("version_number"),
            comment_count=file_data.get("comment_count"),
            content_created_at=file_data.get("content_created_at"),
            content_modified_at=file_data.get("content_modified_at"),
            created_by=file_data.get("created_by"),
            modified_by=file_data.get("modified_by"),
            owned_by=file_data.get("owned_by"),
            item_status=file_data.get("item_status"),
            shared_link=file_data.get("shared_link"),
            tags=file_data.get("tags", []),
            has_collaborations=file_data.get("has_collaborations"),
            permissions=file_data.get("permissions"),
            lock=file_data.get("lock"),
            permalink_url=f"https://app.box.com/file/{file_data['id']}",
            etag=file_data.get("etag"),
            sequence_id=file_data.get("sequence_id"),
        )

        # Process the file entity (download, extract text, chunk)
        # Skip Box Notes (proprietary format) and files without download permission
        permissions = file_data.get("permissions") or {}
        can_download = permissions.get("can_download", False)

        if is_box_note:
            # For Box Notes, yield as-is (metadata only, no content extraction)
            self.logger.debug(f"Skipping Box Note (proprietary format): {file_name}")
            yield file_entity
        elif not can_download:
            # File doesn't have download permissions
            self.logger.debug(
                f"Skipping file without download permission: {file_name} ({file_data['id']})"
            )
            yield file_entity
        else:
            # File can be downloaded - download it using file downloader
            try:
                await self.file_downloader.download_from_url(
                    entity=file_entity,
                    http_client_factory=self.http_client,
                    access_token_provider=self.get_access_token,
                    logger=self.logger,
                )

                # Verify download succeeded
                if not file_entity.local_path:
                    raise ValueError(f"Download failed - no local path set for {file_entity.name}")

                self.logger.debug(f"Successfully downloaded file: {file_entity.name}")
                yield file_entity

            except FileSkippedException as e:
                # File intentionally skipped (unsupported type, too large, etc.) - not an error
                self.logger.debug(f"Skipping file: {e.reason}")
                yield file_entity

            except Exception as e:
                self.logger.warning(f"Failed to download file {file_name} ({file_data['id']}): {e}")
                # Still yield the file entity without processed content
                yield file_entity

        file_breadcrumb = Breadcrumb(
            entity_id=file_entity.file_id,
            name=file_entity.name,
            entity_type="BoxFileEntity",
        )
        file_breadcrumbs = [*breadcrumbs, file_breadcrumb]

        # Generate comments for this file
        async for comment_entity in self._generate_comment_entities(
            client, file_data["id"], file_data.get("name", ""), file_breadcrumbs
        ):
            yield comment_entity

        # Generate collaborations for this file
        async for collab_entity in self._generate_collaboration_entities(
            client, file_data["id"], "file", file_data.get("name", ""), file_breadcrumbs
        ):
            yield collab_entity

    async def _generate_comment_entities(
        self,
        client: httpx.AsyncClient,
        file_id: str,
        file_name: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate comment entities for a file.

        Args:
            client: HTTP client to use
            file_id: Box file ID
            file_name: Name of the file
            breadcrumbs: Parent breadcrumbs

        Yields:
            Comment entities
        """
        try:
            comment_fields = (
                "id,message,created_by,created_at,modified_at,is_reply_comment,tagged_message"
            )
            comments_data = await self._get_with_auth(
                client,
                f"{self.API_BASE}/files/{file_id}/comments",
                params={"fields": comment_fields},
            )

            if not comments_data or not comments_data.get("entries"):
                return

            for comment in comments_data.get("entries", []):
                # Create comment name from message preview
                message = comment.get("message", "")
                comment_name = message[:50] + "..." if len(message) > 50 else message
                if not comment_name:
                    comment_name = f"Comment {comment['id']}"

                yield BoxCommentEntity(
                    comment_id=comment["id"],
                    breadcrumbs=breadcrumbs,
                    name=comment_name,
                    created_at=comment.get("created_at"),
                    updated_at=comment.get("modified_at"),
                    file_id=file_id,
                    file_name=file_name,
                    message=message,
                    created_by=comment.get("created_by", {}),
                    is_reply_comment=comment.get("is_reply_comment", False),
                    tagged_message=comment.get("tagged_message"),
                )

        except Exception as e:
            self.logger.debug(f"Failed to get comments for file {file_id}: {e}")

    async def _generate_collaboration_entities(
        self,
        client: httpx.AsyncClient,
        item_id: str,
        item_type: str,
        item_name: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate collaboration entities for a file or folder.

        Args:
            client: HTTP client to use
            item_id: Box item ID (file or folder)
            item_type: Type of item ("file" or "folder")
            item_name: Name of the item
            breadcrumbs: Parent breadcrumbs

        Yields:
            Collaboration entities
        """
        try:
            collab_fields = (
                "id,role,accessible_by,item,status,created_at,modified_at,created_by,"
                "expires_at,is_access_only,invite_email,acknowledged_at"
            )
            collabs_data = await self._get_with_auth(
                client,
                f"{self.API_BASE}/{item_type}s/{item_id}/collaborations",
                params={"fields": collab_fields},
            )

            if not collabs_data or not collabs_data.get("entries"):
                return

            for collab in collabs_data.get("entries", []):
                # Create collaboration name from role and accessible_by
                accessible_by = collab.get("accessible_by", {})
                accessible_name = accessible_by.get("name", accessible_by.get("login", "Unknown"))
                role = collab.get("role", "")
                collab_name = f"{role} - {accessible_name}"

                yield BoxCollaborationEntity(
                    collaboration_id=collab["id"],
                    breadcrumbs=breadcrumbs,
                    name=collab_name,
                    created_at=collab.get("created_at"),
                    updated_at=collab.get("modified_at"),
                    role=role,
                    accessible_by=accessible_by,
                    item=collab.get("item", {}),
                    item_id=item_id,
                    item_type=item_type,
                    item_name=item_name,
                    status=collab.get("status", ""),
                    created_by=collab.get("created_by"),
                    expires_at=collab.get("expires_at"),
                    is_access_only=collab.get("is_access_only"),
                    invite_email=collab.get("invite_email"),
                    acknowledged_at=collab.get("acknowledged_at"),
                )

        except Exception as e:
            self.logger.debug(f"Failed to get collaborations for {item_type} {item_id}: {e}")

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Box.

        This method orchestrates the entire sync process:
        1. Get current user information
        2. Recursively sync folders and files starting from root or specified folder
        3. For each file, sync comments and collaborations
        """
        self.logger.debug("Starting Box sync")

        async with self.http_client() as client:
            # Get current user
            current_user = await self._get_current_user(client)
            if current_user:
                user_entity = await self._generate_user_entity(client, current_user["id"])
                if user_entity:
                    self.logger.debug(f"Syncing Box for user: {current_user.get('name')}")
                    yield user_entity

            # Start recursive sync from the specified folder (default is root "0")
            self.logger.debug(f"Starting folder sync from folder ID: {self.folder_id}")
            async for entity in self._generate_folder_entities(client, self.folder_id, []):
                yield entity

        self.logger.debug("Box sync completed")

    async def validate(self) -> bool:
        """Verify OAuth2 token by pinging Box's /users/me endpoint.

        Returns:
            True if credentials are valid, False otherwise
        """
        return await self._validate_oauth2(
            ping_url=f"{self.API_BASE}/users/me",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
