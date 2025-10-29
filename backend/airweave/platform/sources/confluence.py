"""Confluence source implementation.

Retrieves data (read-only) from a user's Confluence instance:
  - Spaces
  - Pages (and their children)
  - Blog Posts
  - Comments
  - Labels
  - Tasks
  - Whiteboards
  - Custom Content
  - Databases
  - Folders

References:
    https://developer.atlassian.com/cloud/confluence/rest/v2/intro/
    https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-spaces/
"""

from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from airweave.core.exceptions import TokenRefreshError
from airweave.core.logging import logger
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.confluence import (
    ConfluenceBlogPostEntity,
    ConfluenceCommentEntity,
    ConfluenceDatabaseEntity,
    ConfluenceFolderEntity,
    ConfluenceLabelEntity,
    ConfluencePageEntity,
    ConfluenceSpaceEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Confluence",
    short_name="confluence",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    auth_config_class=None,
    config_class="ConfluenceConfig",
    labels=["Knowledge Base", "Documentation"],
    supports_continuous=False,
)
class ConfluenceSource(BaseSource):
    """Confluence source connector integrates with the Confluence REST API to extract content.

    Connects to your Confluence instance.

    It supports syncing spaces, pages, blog posts, comments, labels, and other
    content types. It converts Confluence pages to HTML format for content extraction and
    extracts embedded files and attachments from page content.
    """

    @staticmethod
    async def _get_accessible_resources(access_token: str) -> list[dict]:
        """Get the list of accessible Atlassian resources for this token.

        Args:
            access_token: The OAuth access token

        Returns:
            list[dict]: List of accessible resources, each containing 'id' and 'url' keys

        Raises:
            TokenRefreshError: If authentication fails (401/403), indicating token is invalid
        """
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
            try:
                response = await client.get(
                    "https://api.atlassian.com/oauth/token/accessible-resources", headers=headers
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                # Authentication failures should bubble up to mark connection as unauthenticated
                if e.response.status_code in (401, 403):
                    logger.error(
                        f"Authentication failed getting accessible resources: "
                        f"{e.response.status_code} - Token is invalid or expired"
                    )
                    raise TokenRefreshError(
                        f"Failed to access Atlassian resources: {e.response.status_code} {e.response.reason_phrase}"
                    ) from e
                # Other HTTP errors - log and return empty (maybe network issues, temporary errors)
                logger.error(f"HTTP error getting accessible resources: {str(e)}")
                return []
            except Exception as e:
                # Other exceptions (network, timeout, etc.) - log and return empty
                logger.error(f"Error getting accessible resources: {str(e)}")
                return []

    @staticmethod
    async def _extract_cloud_id(access_token: str) -> tuple[str, str]:
        """Extract the Atlassian Cloud ID from OAuth 2.0 accessible-resources.

        Args:
            access_token: The OAuth access token

        Returns:
            cloud_id (str): The cloud instance ID
        """
        try:
            resources = await ConfluenceSource._get_accessible_resources(access_token)

            if not resources:
                logger.warning("No accessible resources found")
                return ""

            # Use the first available resource
            # In most cases, there will only be one resource
            resource = resources[0]
            cloud_id = resource.get("id", "")

            if not cloud_id:
                logger.warning("Missing ID in accessible resources")
            return cloud_id

        except TokenRefreshError:
            # Re-raise auth errors - these indicate invalid/expired credentials
            raise
        except Exception as e:
            # Other errors (network, parsing, etc.) - log and return empty
            logger.error(f"Error extracting cloud ID: {str(e)}")
            return ""

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "ConfluenceSource":
        """Create a new Confluence source instance."""
        instance = cls()
        instance.access_token = access_token
        instance.cloud_id = await cls._extract_cloud_id(access_token)
        instance.base_url = f"https://api.atlassian.com/ex/confluence/{instance.cloud_id}"
        logger.info(f"Initialized Confluence source with base URL: {instance.base_url}")
        return instance

    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Any:
        """Make an authenticated GET request to the Confluence REST API using the provided URL.

        By default, we're using OAuth 2.0 with refresh tokens for authentication.
        """
        access_token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "X-Atlassian-Token": "no-check",  # Required for CSRF protection
        }

        # Add cloud instance ID if available
        if self.cloud_id:
            headers["X-Cloud-ID"] = self.cloud_id

        self.logger.debug(f"Making request to {url} with headers: {headers}")

        try:
            response = await client.get(url, headers=headers)
        except httpx.HTTPStatusError as e:
            # Handle 401 Unauthorized - try refreshing token
            if e.response.status_code == 401 and self._token_manager:
                self.logger.info("Received 401 error, attempting to refresh token")
                refreshed = await self._token_manager.refresh_on_unauthorized()

                if refreshed:
                    # Retry with new token
                    new_access_token = await self.get_access_token()
                    headers["Authorization"] = f"Bearer {new_access_token}"
                    self.logger.info("Retrying request with refreshed token")
                    response = await client.get(url, headers=headers)
                else:
                    raise
            else:
                raise

        if not response.is_success:
            self.logger.error(f"Request failed with status {response.status_code}")
            self.logger.error(f"Response headers: {dict(response.headers)}")
            self.logger.error(f"Response body: {response.text}")

            # Special handling for scope-related errors
            if response.status_code == 401:
                error_body = response.json() if response.text else {}
                error_message = error_body.get("message", "")

                if (
                    "scope" in error_message.lower()
                    or "x-failure-category" in response.headers
                    and "SCOPE" in response.headers.get("x-failure-category", "")
                ):
                    self.logger.error(
                        "OAuth scope error. The token doesn't have the required permissions."
                    )
                    self.logger.error(
                        "Please verify that your OAuth app has the correct scopes configured."
                    )
                    raise ValueError(f"OAuth scope error: {error_message}.")

        response.raise_for_status()
        return response.json()

    async def _generate_space_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ConfluenceSpaceEntity, None]:
        """Generate ConfluenceSpaceEntity objects.

        This method generates ConfluenceSpaceEntity objects for all spaces in the user's Confluence
            instance. It uses cursor-based pagination to retrieve all spaces.

        Source: https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-space/#api-spaces-get

        Args:
        -----
            client: The HTTP client to use for the request

        Returns:
        --------
            AsyncGenerator[ConfluenceSpaceEntity, None]: An asynchronous generator of
                ConfluenceSpaceEntity objects
        """
        limit = 50
        url = f"{self.base_url}/wiki/api/v2/spaces?limit={limit}"
        while url:
            data = await self._get_with_auth(client, url)
            for space in data.get("results", []):
                yield ConfluenceSpaceEntity(
                    # Base fields
                    entity_id=space["id"],
                    breadcrumbs=[],
                    name=space.get("name"),
                    created_at=space.get("createdAt"),
                    updated_at=space.get("updatedAt"),
                    # API fields
                    space_key=space["key"],
                    space_type=space.get("type"),
                    description=space.get("description"),
                    status=space.get("status"),
                    homepage_id=space.get("homepageId"),
                )

            # Cursor-based pagination (check for next link)
            next_link = data.get("_links", {}).get("next")
            url = f"{self.base_url}{next_link}" if next_link else None

    async def _generate_page_entities(
        self, client: httpx.AsyncClient, space_id: str, space_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[ConfluencePageEntity, None]:
        """Generate ConfluencePageEntity objects for a space."""
        limit = 50
        url = f"{self.base_url}/wiki/api/v2/spaces/{space_id}/pages?limit={limit}"

        while url:
            data = await self._get_with_auth(client, url)

            for page in data.get("results", []):
                page_breadcrumbs = [space_breadcrumb]
                page_id = page["id"]

                # Get detailed page content with expanded body
                page_detail_url = f"{self.base_url}/wiki/api/v2/pages/{page_id}?body-format=storage"
                page_details = await self._get_with_auth(client, page_detail_url)

                # Extract full body content
                body_content = page_details.get("body", {}).get("storage", {}).get("value", "")

                # Add ".html" extension to the filename
                page_title = page_details.get("title", "Untitled Page")
                filename_with_extension = page_title

                # Create download URL for content extraction
                download_url = f"{self.base_url}/wiki/api/v2/pages/{page_id}"

                file_entity = ConfluencePageEntity(
                    # Base fields
                    entity_id=page["id"],
                    breadcrumbs=page_breadcrumbs,
                    name=filename_with_extension,
                    created_at=page_details.get("createdAt"),
                    updated_at=page_details.get("updatedAt"),
                    # File fields
                    url=download_url,
                    size=0,  # Content is in local file
                    file_type="html",
                    mime_type="text/html",
                    local_path=None,  # Will be set after saving HTML content
                    # API fields
                    content_id=page["id"],
                    title=page_details.get("title"),
                    space_id=page_details.get("space", {}).get("id"),
                    body=body_content,
                    version=page_details.get("version", {}).get("number"),
                    status=page_details.get("status"),
                )

                # Create HTML file content with full body
                html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{page_details.get("title", "")}</title>
                    <meta charset="UTF-8">
                </head>
                <body>
                    {body_content}
                </body>
                </html>
                """

                # Save HTML content to file using file downloader
                try:
                    await self.file_downloader.save_bytes(
                        entity=file_entity,
                        content=html_content.encode("utf-8"),
                        filename_with_extension=filename_with_extension + ".html",
                        logger=self.logger,
                    )

                    # Verify save succeeded
                    if not file_entity.local_path:
                        raise ValueError(f"Save failed - no local path set for {file_entity.name}")

                    self.logger.debug(f"Successfully saved page HTML: {file_entity.name}")
                    yield file_entity

                except Exception as e:
                    self.logger.warning(f"Failed to save page {page_title}: {e}")
                    # Skip this page on save failure
                    continue

            # Handle pagination
            next_link = data.get("_links", {}).get("next")
            url = f"{self.base_url}{next_link}" if next_link else None

    async def _generate_blog_post_entities(
        self, client: httpx.AsyncClient, space_id: str, space_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate ConfluenceBlogPostEntity objects."""
        limit = 50
        url = f"{self.base_url}/wiki/api/v2/spaces/{space_id}/blogposts?limit={limit}"
        while url:
            data = await self._get_with_auth(client, url)
            for blog in data.get("results", []):
                yield ConfluenceBlogPostEntity(
                    # Base fields
                    entity_id=blog["id"],
                    breadcrumbs=[space_breadcrumb],
                    name=blog.get("title", "Untitled Blog Post"),
                    created_at=blog.get("createdAt"),
                    updated_at=blog.get("updatedAt"),
                    # API fields
                    content_id=blog["id"],
                    title=blog.get("title"),
                    space_id=blog.get("spaceId"),
                    body=(blog.get("body", {}).get("storage", {}).get("value")),
                    version=blog.get("version", {}).get("number"),
                    status=blog.get("status"),
                )

            next_link = data.get("_links", {}).get("next")
            url = f"{self.base_url}{next_link}" if next_link else None

    async def _generate_comment_entities(
        self, client: httpx.AsyncClient, page_id: str, parent_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate ConfluenceCommentEntity objects for a given content (page, blog, etc.).

        For example:
          GET /wiki/api/v2/pages/{page_id}/inline-comments
        or
          GET /wiki/api/v2/blogposts/{blog_id}/inline-comments
        depending on the content type.
        """
        # Example: retrieving comments for a page
        limit = 50
        url = f"{self.base_url}/wiki/api/v2/pages/{page_id}/inline-comments?limit={limit}"
        while url:
            data = await self._get_with_auth(client, url)
            for comment in data.get("results", []):
                # Extract comment text and create name
                comment_text = comment.get("body", {}).get("storage", {}).get("value", "")
                # Strip HTML for preview
                import re

                text_preview = re.sub(r"<[^>]+>", "", comment_text)[:50]
                comment_name = text_preview + "..." if len(text_preview) == 50 else text_preview
                if not comment_name:
                    comment_name = f"Comment {comment['id']}"

                yield ConfluenceCommentEntity(
                    # Base fields
                    entity_id=comment["id"],
                    breadcrumbs=parent_breadcrumbs,
                    name=comment_name,
                    created_at=comment.get("createdAt"),
                    updated_at=comment.get("updatedAt"),
                    # API fields
                    parent_content_id=comment.get("container", {}).get("id"),
                    text=comment_text,
                    created_by=comment.get("createdBy"),
                    status=comment.get("status"),
                )
            next_link = data.get("_links", {}).get("next")
            url = f"{self.base_url}{next_link}" if next_link else None

    # You can define similar methods for label, task, whiteboard, custom content, etc.
    # For example:
    async def _generate_label_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate ConfluenceLabelEntity objects."""
        # The Confluence v2 REST API for labels is still evolving; example endpoint:
        url = "https://your-domain.atlassian.net/wiki/api/v2/labels?limit=50"
        while url:
            data = await self._get_with_auth(client, url)
            for label_obj in data.get("results", []):
                yield ConfluenceLabelEntity(
                    # Base fields
                    entity_id=label_obj["id"],
                    breadcrumbs=[],
                    name=label_obj.get("name", ""),
                    created_at=None,  # Labels don't have creation timestamp
                    updated_at=None,  # Labels don't have update timestamp
                    # API fields
                    label_type=label_obj.get("type"),
                    owner_id=label_obj.get("ownerId"),
                )
            next_link = data.get("_links", {}).get("next")
            url = f"https://your-domain.atlassian.net{next_link}" if next_link else None

    # Similar approach for tasks, whiteboards, custom content...
    # The actual endpoints may differ, but the pattern of pagination remains the same.

    async def _generate_database_entities(
        self, client: httpx.AsyncClient, space_key: str, space_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate ConfluenceDatabaseEntity objects for a given space."""
        url = f"https://your-domain.atlassian.net/wiki/api/v2/spaces/{space_key}/databases?limit=50"
        while url:
            data = await self._get_with_auth(client, url)
            for database in data.get("results", []):
                yield ConfluenceDatabaseEntity(
                    # Base fields
                    entity_id=database["id"],
                    breadcrumbs=[space_breadcrumb],
                    name=database.get("title", "Untitled Database"),
                    created_at=database.get("createdAt"),
                    updated_at=database.get("updatedAt"),
                    # API fields
                    content_id=database["id"],
                    title=database.get("title"),
                    space_key=space_key,
                    description=database.get("description"),
                    status=database.get("status"),
                )
            next_link = data.get("_links", {}).get("next")
            url = f"https://your-domain.atlassian.net{next_link}" if next_link else None

    async def _generate_folder_entities(
        self, client: httpx.AsyncClient, space_id: str, space_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate ConfluenceFolderEntity objects for a given space."""
        url = f"{self.base_url}/wiki/api/v2/spaces/{space_id}/content/folder?limit=50"
        while url:
            data = await self._get_with_auth(client, url)
            for folder in data.get("results", []):
                yield ConfluenceFolderEntity(
                    # Base fields
                    entity_id=folder["id"],
                    breadcrumbs=[space_breadcrumb],
                    name=folder.get("title", "Untitled Folder"),
                    created_at=folder.get("createdAt"),
                    updated_at=folder.get("updatedAt"),
                    # API fields
                    content_id=folder["id"],
                    title=folder.get("title"),
                    space_key=space_id,
                    status=folder.get("status"),
                )
            next_link = data.get("_links", {}).get("next")
            url = f"{self.base_url}{next_link}" if next_link else None

    async def validate(self) -> bool:
        """Verify Confluence OAuth2 token and site access by pinging a lightweight endpoint."""
        # Ensure we have a cloud_id/base_url; if missing, try to resolve from the current token.
        if not getattr(self, "cloud_id", None) or not getattr(self, "base_url", None):
            token = await self.get_access_token()
            if not token:
                self.logger.error("Confluence validation failed: no access token available.")
                return False
            cloud_id = await self._extract_cloud_id(token)
            if not cloud_id:
                self.logger.error(
                    "Confluence validation failed: unable to resolve Atlassian cloud ID."
                )
                return False
            self.cloud_id = cloud_id
            self.base_url = f"https://api.atlassian.com/ex/confluence/{cloud_id}"

        # Simple authorized ping against spaces (validates scopes and site reachability).
        return await self._validate_oauth2(
            ping_url=f"{self.base_url}/wiki/api/v2/spaces?limit=1",
            headers={
                "Accept": "application/json",
                "X-Atlassian-Token": "no-check",
                "X-Cloud-ID": self.cloud_id,
            },
            timeout=10.0,
        )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:  # noqa: C901
        """Generate all Confluence content."""
        async with httpx.AsyncClient() as client:
            # 1) Yield all spaces (top-level)
            async for space_entity in self._generate_space_entities(client):
                yield space_entity

                space_breadcrumb = Breadcrumb(entity_id=space_entity.entity_id)

                # 2) For each space, yield pages and their children
                async for page_entity in self._generate_page_entities(
                    client,
                    space_id=space_entity.entity_id,
                    space_breadcrumb=space_breadcrumb,
                ):
                    # Skip if page_entity is None (failed to process)
                    if page_entity is None:
                        continue

                    yield page_entity

                    page_breadcrumbs = [
                        space_breadcrumb,
                        Breadcrumb(entity_id=page_entity.entity_id),
                    ]
                    # 3) For each page, yield comments
                    async for comment_entity in self._generate_comment_entities(
                        client,
                        page_id=page_entity.content_id,
                        parent_breadcrumbs=page_breadcrumbs,
                    ):
                        yield comment_entity

                # 4) For each space, yield databases
                # async for database_entity in self._generate_database_entities(
                #     client,
                #     space_key=space_entity.entity_id,
                #     space_breadcrumb=space_breadcrumb,
                # ):
                #     yield database_entity

                # 5) For each space, yield folders
                # async for folder_entity in self._generate_folder_entities(
                #     client,
                #     space_key=space_entity.entity_id,
                #     space_breadcrumb=space_breadcrumb,
                # ):
                #     yield folder_entity

                # 6) For each space, yield blog posts and their comments
                async for blog_entity in self._generate_blog_post_entities(
                    client, space_id=space_entity.entity_id, space_breadcrumb=space_breadcrumb
                ):
                    yield blog_entity

                    # blog_breadcrumb = Breadcrumb(
                    #     entity_id=blog_entity.entity_id,
                    #     name=blog_entity.title or "",
                    #     type="blogpost",
                    # )
                    # async for comment_entity in self._generate_comment_entities(
                    #     client,
                    #     content_id=blog_entity.entity_id,
                    #     parent_breadcrumbs=[blog_breadcrumb],
                    # ):
                    #     yield comment_entity

                # TODO: Add support for labels, tasks, whiteboards, custom content
                # # 7) Yield labels (global or any label scope)
                # async for label_entity in self._generate_label_entities(client):
                #     yield label_entity

                # # 8) Yield tasks
                # async for task_entity in self._generate_task_entities(client):
                #     yield task_entity

                # # 9) Yield whiteboards
                # async for whiteboard_entity in self._generate_whiteboard_entities(client):
                #     yield whiteboard_entity

                # # 10) Yield custom content
                # async for custom_content_entity in self._generate_custom_content_entities(client):
                #     yield custom_content_entity
