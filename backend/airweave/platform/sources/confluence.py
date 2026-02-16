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
from tenacity import retry, stop_after_attempt

from airweave.core.exceptions import TokenRefreshError
from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.config import ConfluenceConfig
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
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.storage import FileSkippedException
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Confluence",
    short_name="confluence",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_ROTATING_REFRESH,
    auth_config_class=None,
    config_class=ConfluenceConfig,
    labels=["Knowledge Base", "Documentation"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class ConfluenceSource(BaseSource):
    """Confluence source connector integrates with the Confluence REST API to extract content.

    Connects to your Confluence instance.

    It supports syncing spaces, pages, blog posts, comments, labels, and other
    content types. It converts Confluence pages to HTML format for content extraction and
    extracts embedded files and attachments from page content.
    """

    async def _get_accessible_resources(self) -> list[dict]:
        """Get the list of accessible Atlassian resources for this token.

        Uses token manager to ensure fresh access token.
        """
        self.logger.debug("Retrieving accessible Atlassian resources")

        # Get fresh access token (will refresh if needed)
        access_token = await self.get_access_token()

        if not access_token:
            self.logger.error("Cannot get accessible resources: access token is None")
            return []

        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
            try:
                self.logger.debug(
                    "Making request to https://api.atlassian.com/oauth/token/accessible-resources"
                )
                response = await client.get(
                    "https://api.atlassian.com/oauth/token/accessible-resources", headers=headers
                )
                response.raise_for_status()
                resources = response.json()
                self.logger.debug(f"Found {len(resources)} accessible Atlassian resources")
                self.logger.debug(f"Resources: {resources}")
                return resources
            except httpx.HTTPStatusError as e:
                self.logger.error(
                    f"HTTP error getting accessible resources: "
                    f"{e.response.status_code} - {e.response.text}"
                )
                return []
            except Exception as e:
                self.logger.error(f"Error getting accessible resources: {str(e)}", exc_info=True)
                return []

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "ConfluenceSource":
        """Create a new Confluence source instance."""
        instance = cls()
        instance.access_token = access_token
        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
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

        self.logger.debug(f"Request headers: {headers}")
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            # Handle 401 Unauthorized - try refreshing token
            if e.response.status_code == 401 and self._token_manager:
                self.logger.warning(
                    "🔐 Received 401 Unauthorized from Confluence - attempting token refresh"
                )
                try:
                    refreshed = await self._token_manager.refresh_on_unauthorized()

                    if refreshed:
                        # Retry with new token (the retry decorator will handle this)
                        self.logger.debug("✅ Token refreshed successfully, retrying request")
                        raise  # Let tenacity retry with the refreshed token
                except TokenRefreshError as refresh_error:
                    # Token refresh failed - provide clear error message
                    self.logger.error(
                        f"❌ Token refresh failed: {str(refresh_error)}. "
                        f"User may need to reconnect their Confluence account."
                    )
                    # Re-raise with clearer context
                    raise TokenRefreshError(
                        f"Failed to refresh Confluence access token: {str(refresh_error)}. "
                        f"Please reconnect your Confluence account."
                    ) from refresh_error

            # Log the error details
            self.logger.error(f"Request failed: {str(e)}")
            self.logger.error(f"Response body: {e.response.text}")
            raise

    async def _generate_space_entities(
        self, client: httpx.AsyncClient, site_url: str
    ) -> AsyncGenerator[ConfluenceSpaceEntity, None]:
        """Generate ConfluenceSpaceEntity objects.

        This method generates ConfluenceSpaceEntity objects for all spaces in the user's Confluence
            instance. It uses cursor-based pagination to retrieve all spaces.

        Source: https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-space/#api-spaces-get

        Args:
        -----
            client: The HTTP client to use for the request
            site_url: The Confluence site URL

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
                    space_id=space["id"],
                    space_name=space["name"],
                    space_key=space["key"],
                    space_type=space.get("type"),
                    description=space.get("description"),
                    status=space.get("status"),
                    homepage_id=space.get("homepageId"),
                    site_url=site_url,
                )

            # Cursor-based pagination (check for next link)
            next_link = data.get("_links", {}).get("next")
            url = f"{self.base_url}{next_link}" if next_link else None

    async def _generate_page_entities(
        self,
        client: httpx.AsyncClient,
        space_id: str,
        space_key: str,
        space_breadcrumb: Breadcrumb,
        site_url: str,
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
                    title=page_details.get("title", "Untitled"),
                    space_id=page_details.get("space", {}).get("id"),
                    space_key=space_key,
                    body=body_content,
                    version=page_details.get("version", {}).get("number"),
                    status=page_details.get("status"),
                    site_url=site_url,
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

                except FileSkippedException as e:
                    # File intentionally skipped (unsupported type, too large, etc.) - not an error
                    self.logger.debug(f"Skipping file: {e.reason}")
                    continue

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
        self,
        client: httpx.AsyncClient,
        page_id: str,
        parent_breadcrumbs: List[Breadcrumb],
        parent_space_key: str,
        site_url: str,
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
                    comment_id=comment["id"],
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
                    name=label_obj.get("name"),
                    created_at=None,  # Labels don't have creation timestamp
                    updated_at=None,  # Labels don't have update timestamp
                    # API fields
                    label_id=label_obj["id"],
                    label_name=label_obj["name"],
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
        """Verify Confluence OAuth2 token by calling accessible-resources endpoint.

        A successful call proves the token is valid and has necessary scopes.
        Cloud ID extraction happens lazily during sync.
        """
        try:
            resources = await self._get_accessible_resources()

            if not resources:
                self.logger.error("Confluence validation failed: no accessible resources found")
                return False

            self.logger.debug("✅ Confluence validation successful")
            return True

        except Exception as e:
            self.logger.error(f"Confluence validation failed: {str(e)}")
            return False

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:  # noqa: C901
        """Generate all Confluence content."""
        self.logger.debug("Starting Confluence entity generation process")

        resources = await self._get_accessible_resources()
        if not resources:
            raise ValueError("No accessible resources found")
        cloud_id = resources[0]["id"]
        site_url = resources[0].get("url", "")  # e.g., https://your-domain.atlassian.net

        self.base_url = f"https://api.atlassian.com/ex/confluence/{cloud_id}"
        self.logger.debug(f"Base URL set to: {self.base_url}")
        self.logger.debug(f"Site URL: {site_url}")
        async with httpx.AsyncClient() as client:
            # 1) Yield all spaces (top-level)
            async for space_entity in self._generate_space_entities(client, site_url):
                yield space_entity

                space_breadcrumb = Breadcrumb(
                    entity_id=space_entity.entity_id,
                    name=space_entity.space_name or space_entity.space_key,
                    entity_type=ConfluenceSpaceEntity.__name__,
                )

                # 2) For each space, yield pages and their children
                async for page_entity in self._generate_page_entities(
                    client,
                    space_id=space_entity.entity_id,
                    space_key=space_entity.space_key,
                    space_breadcrumb=space_breadcrumb,
                    site_url=site_url,
                ):
                    # Skip if page_entity is None (failed to process)
                    if page_entity is None:
                        continue

                    yield page_entity

                    page_breadcrumbs = [
                        space_breadcrumb,
                        Breadcrumb(
                            entity_id=page_entity.entity_id,
                            name=page_entity.title or page_entity.name or "Untitled Page",
                            entity_type=ConfluencePageEntity.__name__,
                        ),
                    ]
                    # 3) For each page, yield comments
                    async for comment_entity in self._generate_comment_entities(
                        client,
                        page_id=page_entity.content_id,
                        parent_breadcrumbs=page_breadcrumbs,
                        parent_space_key=space_entity.space_key,
                        site_url=site_url,
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
