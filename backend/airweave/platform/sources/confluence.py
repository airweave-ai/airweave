"""Confluence source implementation.

Retrieves data (read-only) from a user's Confluence instance:
  - Spaces
  - Pages (and their children)
  - Blog Posts
  - Comments
  - Labels
  - Databases
  - Folders

References:
    https://developer.atlassian.com/cloud/confluence/rest/v2/intro/
    https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-spaces/
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
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
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup

ATLASSIAN_ACCESSIBLE_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"


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

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: ConfluenceConfig,
    ) -> ConfluenceSource:
        """Create a new Confluence source instance."""
        return cls(auth=auth, logger=logger, http_client=http_client)

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _authed_headers(self) -> Dict[str, str]:
        """Build Authorization + Accept headers with a fresh token."""
        token = await self.auth.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "X-Atlassian-Token": "no-check",
        }

    async def _refresh_and_get_headers(self) -> Dict[str, str]:
        """Force-refresh the token and return updated headers."""
        new_token = await self.auth.force_refresh()
        return {
            "Authorization": f"Bearer {new_token}",
            "Accept": "application/json",
            "X-Atlassian-Token": "no-check",
        }

    async def _get_accessible_resources(self) -> list[dict]:
        """Get the list of accessible Atlassian resources for this token."""
        self.logger.debug("Retrieving accessible Atlassian resources")
        resources = await self._get(ATLASSIAN_ACCESSIBLE_RESOURCES_URL)
        self.logger.debug(f"Found {len(resources)} accessible Atlassian resources")
        return resources

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str) -> Any:
        """Make an authenticated GET request to the Confluence REST API.

        Uses OAuth 2.0 with rotating refresh tokens.  On 401, attempts a
        single token refresh before letting ``raise_for_status`` translate
        the response into a ``SourceAuthError``.
        """
        headers = await self._authed_headers()
        response = await self.http_client.get(url, headers=headers)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning("Received 401 from Confluence — attempting token refresh")
            headers = await self._refresh_and_get_headers()
            response = await self.http_client.get(url, headers=headers)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    # ------------------------------------------------------------------
    # Entity generators
    # ------------------------------------------------------------------

    async def _generate_space_entities(
        self, site_url: str
    ) -> AsyncGenerator[ConfluenceSpaceEntity, None]:
        """Generate ConfluenceSpaceEntity objects for all spaces."""
        limit = 50
        url = f"{self._base_url}/wiki/api/v2/spaces?limit={limit}"
        while url:
            data = await self._get(url)
            for space in data.get("results", []):
                yield ConfluenceSpaceEntity.from_api(space, site_url=site_url)

            next_link = data.get("_links", {}).get("next")
            url = f"{self._base_url}{next_link}" if next_link else None

    async def _generate_page_entities(
        self,
        space_id: str,
        space_key: str,
        space_breadcrumb: Breadcrumb,
        site_url: str,
        files: FileService | None = None,
    ) -> AsyncGenerator[ConfluencePageEntity, None]:
        """Generate ConfluencePageEntity objects for a space."""
        limit = 50
        url = f"{self._base_url}/wiki/api/v2/spaces/{space_id}/pages?limit={limit}"

        while url:
            data = await self._get(url)

            for page in data.get("results", []):
                page_id = page["id"]

                page_detail_url = (
                    f"{self._base_url}/wiki/api/v2/pages/{page_id}?body-format=storage"
                )
                page_details = await self._get(page_detail_url)

                file_entity = ConfluencePageEntity.from_api(
                    page_details,
                    breadcrumbs=[space_breadcrumb],
                    space_key=space_key,
                    site_url=site_url,
                    base_url=self._base_url,
                )

                body_content = file_entity.body or ""
                html_content = (
                    f"<!DOCTYPE html>\n<html>\n<head>\n"
                    f"    <title>{file_entity.title or ''}</title>\n"
                    f'    <meta charset="UTF-8">\n</head>\n<body>\n'
                    f"    {body_content}\n</body>\n</html>"
                )

                if files:
                    try:
                        await files.save_bytes(
                            entity=file_entity,
                            content=html_content.encode("utf-8"),
                            filename_with_extension=file_entity.name + ".html",
                            logger=self.logger,
                        )

                        if not file_entity.local_path:
                            raise ValueError(
                                f"Save failed - no local path set for {file_entity.name}"
                            )

                        self.logger.debug(f"Successfully saved page HTML: {file_entity.name}")
                        yield file_entity

                    except FileSkippedException as e:
                        self.logger.debug(f"Skipping file: {e.reason}")
                        continue

                    except SourceAuthError:
                        raise

                    except Exception as e:
                        self.logger.warning(f"Failed to save page {file_entity.name}: {e}")
                        continue
                else:
                    yield file_entity

            next_link = data.get("_links", {}).get("next")
            url = f"{self._base_url}{next_link}" if next_link else None

    async def _generate_blog_post_entities(
        self,
        space_id: str,
        space_breadcrumb: Breadcrumb,
        space_key: str,
        site_url: str,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate ConfluenceBlogPostEntity objects."""
        limit = 50
        url = f"{self._base_url}/wiki/api/v2/spaces/{space_id}/blogposts?limit={limit}"
        while url:
            data = await self._get(url)
            for blog in data.get("results", []):
                yield ConfluenceBlogPostEntity.from_api(
                    blog,
                    breadcrumbs=[space_breadcrumb],
                    space_key=space_key,
                    site_url=site_url,
                )

            next_link = data.get("_links", {}).get("next")
            url = f"{self._base_url}{next_link}" if next_link else None

    async def _generate_comment_entities(
        self,
        page_id: str,
        parent_breadcrumbs: List[Breadcrumb],
        parent_space_key: str,
        site_url: str,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate ConfluenceCommentEntity objects for a page."""
        limit = 50
        url = f"{self._base_url}/wiki/api/v2/pages/{page_id}/inline-comments?limit={limit}"
        while url:
            try:
                data = await self._get(url)
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(f"Failed to fetch comments for page {page_id}: {e}")
                return

            for comment in data.get("results", []):
                yield ConfluenceCommentEntity.from_api(
                    comment,
                    breadcrumbs=parent_breadcrumbs,
                    parent_space_key=parent_space_key,
                    site_url=site_url,
                )
            next_link = data.get("_links", {}).get("next")
            url = f"{self._base_url}{next_link}" if next_link else None

    async def _generate_label_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate ConfluenceLabelEntity objects."""
        url = f"{self._base_url}/wiki/api/v2/labels?limit=50"
        while url:
            data = await self._get(url)
            for label_obj in data.get("results", []):
                yield ConfluenceLabelEntity.from_api(label_obj)
            next_link = data.get("_links", {}).get("next")
            url = f"{self._base_url}{next_link}" if next_link else None

    async def _generate_database_entities(
        self, space_key: str, space_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate ConfluenceDatabaseEntity objects for a given space."""
        url = f"{self._base_url}/wiki/api/v2/spaces/{space_key}/databases?limit=50"
        while url:
            data = await self._get(url)
            for database in data.get("results", []):
                yield ConfluenceDatabaseEntity.from_api(
                    database, breadcrumbs=[space_breadcrumb], space_key=space_key
                )
            next_link = data.get("_links", {}).get("next")
            url = f"{self._base_url}{next_link}" if next_link else None

    async def _generate_folder_entities(
        self, space_id: str, space_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate ConfluenceFolderEntity objects for a given space."""
        url = f"{self._base_url}/wiki/api/v2/spaces/{space_id}/content/folder?limit=50"
        while url:
            data = await self._get(url)
            for folder in data.get("results", []):
                yield ConfluenceFolderEntity.from_api(
                    folder, breadcrumbs=[space_breadcrumb], space_key=space_id
                )
            next_link = data.get("_links", {}).get("next")
            url = f"{self._base_url}{next_link}" if next_link else None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def validate(self) -> None:
        """Verify Confluence OAuth2 token by calling accessible-resources endpoint."""
        resources = await self._get_accessible_resources()
        if not resources:
            raise SourceAuthError("Confluence validation failed: no accessible resources found")

    async def generate_entities(  # noqa: C901
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Confluence content."""
        self.logger.debug("Starting Confluence entity generation process")

        resources = await self._get_accessible_resources()
        if not resources:
            raise ValueError("No accessible resources found")
        cloud_id = resources[0]["id"]
        site_url = resources[0].get("url", "")

        self._base_url = f"https://api.atlassian.com/ex/confluence/{cloud_id}"
        self.logger.debug(f"Base URL: {self._base_url}, Site URL: {site_url}")

        async for space_entity in self._generate_space_entities(site_url):
            yield space_entity

            space_breadcrumb = Breadcrumb(
                entity_id=space_entity.entity_id,
                name=space_entity.space_name or space_entity.space_key,
                entity_type=ConfluenceSpaceEntity.__name__,
            )

            async for page_entity in self._generate_page_entities(
                space_id=space_entity.entity_id,
                space_key=space_entity.space_key,
                space_breadcrumb=space_breadcrumb,
                site_url=site_url,
                files=files,
            ):
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
                async for comment_entity in self._generate_comment_entities(
                    page_id=page_entity.content_id,
                    parent_breadcrumbs=page_breadcrumbs,
                    parent_space_key=space_entity.space_key,
                    site_url=site_url,
                ):
                    yield comment_entity

            async for blog_entity in self._generate_blog_post_entities(
                space_id=space_entity.entity_id,
                space_breadcrumb=space_breadcrumb,
                space_key=space_entity.space_key,
                site_url=site_url,
            ):
                yield blog_entity
