"""Microsoft OneNote source implementation.

Retrieves data from Microsoft OneNote, including:
 - User info (authenticated user)
 - Notebooks the user has access to
 - Section groups within notebooks
 - Sections within notebooks/section groups
 - Pages within sections

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/onenote
  https://learn.microsoft.com/en-us/graph/api/onenote-list-notebooks
  https://learn.microsoft.com/en-us/graph/api/notebook-list-sections
  https://learn.microsoft.com/en-us/graph/api/section-list-pages
"""

import re
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.config import OneNoteConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.onenote import (
    OneNoteNotebookEntity,
    OneNotePageFileEntity,
    OneNoteSectionEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.storage import FileSkippedException
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="OneNote",
    short_name="onenote",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_ROTATING_REFRESH,
    auth_config_class=None,
    config_class=OneNoteConfig,
    labels=["Productivity", "Note Taking", "Collaboration"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class OneNoteSource(BaseSource):
    """Microsoft OneNote source connector integrates with the Microsoft Graph API.

    Synchronizes data from Microsoft OneNote including notebooks, sections, and pages.

    It provides comprehensive access to OneNote resources with proper token refresh
    and rate limiting.
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "OneNoteSource":
        """Create a new Microsoft OneNote source instance with the provided OAuth access token.

        Args:
            access_token: OAuth access token for Microsoft Graph API
            config: Optional configuration parameters

        Returns:
            Configured OneNoteSource instance
        """
        instance = cls()
        instance.access_token = access_token
        return instance

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
        params: Optional[dict] = None,
    ) -> dict:
        """Make an authenticated GET request to Microsoft Graph API.

        Args:
            client: HTTP client to use for the request
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response data
        """
        # Get fresh token (will refresh if needed)
        access_token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            response = await client.get(url, headers=headers, params=params)

            # Handle 401 errors by refreshing token and retrying
            if response.status_code == 401:
                self.logger.warning(
                    f"Got 401 Unauthorized from Microsoft Graph API at {url}, refreshing token..."
                )
                await self.refresh_on_unauthorized()

                # Get new token and retry
                access_token = await self.get_access_token()
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                }
                response = await client.get(url, headers=headers, params=params)

            # Handle 429 Rate Limit
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                self.logger.warning(
                    f"Rate limit hit for {url}, waiting {retry_after} seconds before retry"
                )
                import asyncio

                await asyncio.sleep(float(retry_after))
                # Retry after waiting
                response = await client.get(url, headers=headers, params=params)

            response.raise_for_status()
            return response.json()
        except Exception as e:
            # Provide more descriptive error messages for common OAuth scope issues
            error_msg = self._get_descriptive_error_message(url, str(e))
            self.logger.error(f"Error in API request to {url}: {error_msg}")
            raise

    def _get_descriptive_error_message(self, url: str, error: str) -> str:
        """Get descriptive error message for common OAuth scope issues.

        Args:
            url: The API URL that failed
            error: The original error message

        Returns:
            Enhanced error message with helpful guidance
        """
        # Check for 401 Unauthorized errors
        if "401" in error or "Unauthorized" in error:
            if "/onenote/" in url:
                return (
                    f"{error}\n\n"
                    "🔧 OneNote API requires specific OAuth scopes. Please ensure your auth "
                    "provider (Composio, Pipedream, etc.) includes the following scopes:\n"
                    "• Notes.Read - Required to read OneNote notebooks, sections, and pages\n"
                    "• User.Read - Required to access user information\n"
                    "• offline_access - Required for token refresh\n\n"
                    "If using Composio, make sure to add 'Notes.Read' to your OneDrive integration "
                    "scopes."
                )
            elif "/me" in url and "select=" in url:
                return (
                    f"{error}\n\n"
                    "🔧 User profile access requires the User.Read scope. Please ensure your auth "
                    "provider includes this scope in the OAuth configuration."
                )

        # Check for 403 Forbidden errors
        if "403" in error or "Forbidden" in error:
            if "/onenote/" in url:
                return (
                    f"{error}\n\n"
                    "🔧 OneNote access is forbidden. This usually means:\n"
                    "• The Notes.Read scope is missing from your OAuth configuration\n"
                    "• The user hasn't granted permission to access OneNote\n"
                    "• The OneNote service is not available for this user/tenant\n\n"
                    "Please check your OAuth scopes and user permissions."
                )

        # Return original error if no specific guidance available
        return error

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from Microsoft Graph API format.

        Args:
            dt_str: DateTime string from API

        Returns:
            Parsed datetime object or None
        """
        if not dt_str:
            return None
        try:
            if dt_str.endswith("Z"):
                dt_str = dt_str.replace("Z", "+00:00")
            return datetime.fromisoformat(dt_str)
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Error parsing datetime {dt_str}: {str(e)}")
            return None

    def _strip_html_tags(self, html_content: Optional[str]) -> Optional[str]:
        """Strip HTML tags from content for better text search.

        Uses the same pattern as the base entity class for consistency.

        Args:
            html_content: HTML content string

        Returns:
            Plain text content or None
        """
        if not html_content:
            return None
        try:
            # Use the same pattern as BaseEntity._strip_html for consistency
            import html as html_lib

            # Remove HTML tags and unescape entities
            no_tags = re.sub(r"<[^>]+>", " ", html_content)
            text = html_lib.unescape(no_tags)
            # Normalize whitespace
            text = re.sub(r"\s+", " ", text).strip()
            return text if text else None
        except Exception as e:
            self.logger.warning(f"Error stripping HTML tags: {str(e)}")
            return html_content

    async def _generate_notebook_entities_with_sections(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[tuple[OneNoteNotebookEntity, list], None]:
        """Generate OneNoteNotebookEntity objects with their sections data.

        Uses $expand to fetch sections in the same call, reducing API calls by ~22%.

        Args:
            client: HTTP client for API requests

        Yields:
            Tuple of (OneNoteNotebookEntity, sections_data_list)
        """
        self.logger.debug("Starting notebook entity generation with sections")
        url = f"{self.GRAPH_BASE_URL}/me/onenote/notebooks"
        # Use $expand to get sections in the same call, and $select to reduce payload
        params = {
            "$top": 100,
            "$expand": "sections",
            "$select": (
                "id,displayName,isDefault,isShared,userRole,createdDateTime,"
                "lastModifiedDateTime,createdBy,lastModifiedBy,links,self"
            ),
        }

        try:
            notebook_count = 0
            while url:
                self.logger.debug(f"Fetching notebooks from: {url}")
                data = await self._get_with_auth(client, url, params=params)
                notebooks = data.get("value", [])
                self.logger.debug(f"Retrieved {len(notebooks)} notebooks with sections")

                for notebook_data in notebooks:
                    notebook_count += 1
                    notebook_id = notebook_data.get("id")
                    display_name = notebook_data.get("displayName", "Unknown Notebook")

                    self.logger.debug(f"Processing notebook #{notebook_count}: {display_name}")

                    notebook_entity = OneNoteNotebookEntity(
                        breadcrumbs=[],
                        id=notebook_id,
                        name=display_name,
                        created_at=self._parse_datetime(notebook_data.get("createdDateTime")),
                        updated_at=self._parse_datetime(notebook_data.get("lastModifiedDateTime")),
                        display_name=display_name,
                        is_default=notebook_data.get("isDefault"),
                        is_shared=notebook_data.get("isShared"),
                        user_role=notebook_data.get("userRole"),
                        created_by=notebook_data.get("createdBy"),
                        last_modified_by=notebook_data.get("lastModifiedBy"),
                        links=notebook_data.get("links"),
                        self_url=notebook_data.get("self"),
                        web_url_override=(
                            (notebook_data.get("links") or {}).get("oneNoteWebUrl", {}).get("href")
                        ),
                    )

                    # Get sections data from expanded response
                    sections_data = notebook_data.get("sections", [])

                    yield notebook_entity, sections_data

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None  # params are included in the nextLink

            self.logger.debug(f"Completed notebook generation. Total notebooks: {notebook_count}")

        except Exception as e:
            self.logger.error(f"Error generating notebook entities: {str(e)}")
            raise

    async def _generate_section_entities(
        self,
        client: httpx.AsyncClient,
        notebook_id: str,
        notebook_name: str,
        notebook_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[OneNoteSectionEntity, None]:
        """Generate OneNoteSectionEntity objects for sections in a notebook.

        Args:
            client: HTTP client for API requests
            notebook_id: ID of the notebook
            notebook_name: Name of the notebook
            notebook_breadcrumb: Breadcrumb for the notebook

        Yields:
            OneNoteSectionEntity objects
        """
        self.logger.debug(f"Starting section entity generation for notebook: {notebook_name}")
        url = f"{self.GRAPH_BASE_URL}/me/onenote/notebooks/{notebook_id}/sections"
        params = {"$top": 100}

        try:
            section_count = 0
            while url:
                self.logger.debug(f"Fetching sections from: {url}")
                data = await self._get_with_auth(client, url, params=params)
                sections = data.get("value", [])
                self.logger.debug(
                    f"Retrieved {len(sections)} sections for notebook {notebook_name}"
                )

                for section_data in sections:
                    section_count += 1
                    section_id = section_data.get("id")
                    display_name = section_data.get("displayName", "Unknown Section")

                    self.logger.debug(f"Processing section #{section_count}: {display_name}")

                    yield OneNoteSectionEntity(
                        breadcrumbs=[notebook_breadcrumb],
                        id=section_id,
                        name=display_name,
                        created_at=self._parse_datetime(section_data.get("createdDateTime")),
                        updated_at=self._parse_datetime(section_data.get("lastModifiedDateTime")),
                        # API fields
                        notebook_id=notebook_id,
                        parent_section_group_id=section_data.get("parentSectionGroupId"),
                        display_name=display_name,
                        is_default=section_data.get("isDefault"),
                        created_by=section_data.get("createdBy"),
                        last_modified_by=section_data.get("lastModifiedBy"),
                        pages_url=section_data.get("pagesUrl"),
                        web_url_override=(
                            (section_data.get("links") or {}).get("oneNoteWebUrl", {}).get("href")
                        ),
                    )

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None

            self.logger.debug(
                f"Completed section generation for notebook {notebook_name}. "
                f"Total sections: {section_count}"
            )

        except Exception as e:
            self.logger.error(
                f"Error generating section entities for notebook {notebook_name}: {str(e)}"
            )
            # Don't raise - continue with other notebooks

    async def _generate_page_entities(  # noqa: C901
        self,
        client: httpx.AsyncClient,
        section_id: str,
        section_name: str,
        notebook_id: str,
        section_breadcrumbs: list[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate processed OneNote page entities for pages in a section.

        Args:
            client: HTTP client for API requests
            section_id: ID of the section
            section_name: Name of the section
            notebook_id: ID of the notebook
            section_breadcrumbs: Breadcrumbs for the section

        Yields:
            Processed BaseEntity objects (HTML content converted to text)
        """
        self.logger.debug(f"Starting page generation for section: {section_name}")
        url = f"{self.GRAPH_BASE_URL}/me/onenote/sections/{section_id}/pages"
        # Use $select to reduce payload size and improve performance
        params = {
            "$top": 50,
            "$select": "id,title,contentUrl,level,order,createdDateTime,lastModifiedDateTime",
        }

        try:
            page_count = 0
            while url:
                self.logger.debug(f"Fetching pages from: {url}")
                data = await self._get_with_auth(client, url, params=params)
                pages = data.get("value", [])
                self.logger.debug(f"Retrieved {len(pages)} pages for section {section_name}")

                for page_data in pages:
                    page_count += 1
                    page_id = page_data.get("id")
                    title = page_data.get("title", "Untitled Page")
                    content_url = page_data.get("contentUrl")

                    # Skip deleted pages (OneNote API may return deleted items in some cases)
                    if page_data.get("isDeleted") or page_data.get("deleted"):
                        self.logger.debug(f"Skipping deleted page: {title}")
                        continue

                    self.logger.debug(f"Processing page #{page_count}: {title}")

                    # Skip pages without content URL (can't be processed as files)
                    if not content_url:
                        self.logger.warning(f"Skipping page '{title}' - no content URL")
                        continue

                    # Skip empty pages (no title)
                    if not title or title == "Untitled Page":
                        self.logger.debug(f"Skipping empty page '{title}'")
                        continue

                    self.logger.debug(f"Page '{title}': {content_url}")

                    # Add .html extension to title for proper file processing
                    page_name = f"{title}.html" if not title.endswith(".html") else title

                    # Create the file entity
                    file_entity = OneNotePageFileEntity(
                        breadcrumbs=section_breadcrumbs,
                        id=page_id,
                        name=page_name,
                        created_at=self._parse_datetime(page_data.get("createdDateTime")),
                        updated_at=self._parse_datetime(page_data.get("lastModifiedDateTime")),
                        # File fields
                        url=content_url,
                        size=0,  # Content will be downloaded
                        file_type="html",
                        mime_type="text/html",
                        local_path=None,  # Will be set after download
                        # API fields
                        notebook_id=notebook_id,
                        section_id=section_id,
                        title=title,
                        content_url=content_url,
                        level=page_data.get("level"),
                        order=page_data.get("order"),
                        created_by=page_data.get("createdBy"),
                        last_modified_by=page_data.get("lastModifiedBy"),
                        links=page_data.get("links"),
                        user_tags=page_data.get("userTags", []),
                        web_url_override=(
                            (page_data.get("links") or {}).get("oneNoteWebUrl", {}).get("href")
                        ),
                    )

                    # Download the page HTML using file downloader
                    try:
                        await self.file_downloader.download_from_url(
                            entity=file_entity,
                            http_client_factory=self.http_client,
                            access_token_provider=self.get_access_token,
                            logger=self.logger,
                        )

                        # Verify download succeeded
                        if not file_entity.local_path:
                            raise ValueError(
                                f"Download failed - no local path set for {file_entity.name}"
                            )

                        self.logger.debug(f"Successfully downloaded page: {file_entity.name}")
                        yield file_entity

                    except FileSkippedException as e:
                        # Page intentionally skipped (unsupported type, too large, etc.).
                        # Not an error – continue with other pages.
                        self.logger.debug(f"Skipping page {title}: {e.reason}")
                        continue

                    except Exception as e:
                        self.logger.error(f"Failed to download page {title}: {e}")
                        # Continue with other pages
                        continue

                # Handle pagination
                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None

            self.logger.debug(
                f"Completed page generation for section {section_name}. Total pages: {page_count}"
            )

        except Exception as e:
            self.logger.error(f"Error generating pages for section {section_name}: {str(e)}")
            # Don't raise - continue with other sections

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Microsoft OneNote entities.

        Yields entities in the following order:
          - OneNoteNotebookEntity for user's notebooks
          - OneNoteSectionEntity for sections in each notebook
          - OneNotePageFileEntity for pages in each section (processed as HTML files)
        """
        self.logger.debug("===== STARTING MICROSOFT ONENOTE ENTITY GENERATION =====")
        entity_count = 0

        try:
            async with self.http_client() as client:
                self.logger.debug("HTTP client created, starting entity generation")

                # 1) Generate notebook entities with sections (performance optimized)
                self.logger.debug("Generating notebook entities with sections...")
                async for (
                    notebook_entity,
                    sections_data,
                ) in self._generate_notebook_entities_with_sections(client):
                    entity_count += 1
                    self.logger.debug(
                        f"Yielding entity #{entity_count}: Notebook - "
                        f"{notebook_entity.display_name}"
                    )
                    yield notebook_entity

                    # Create notebook breadcrumb
                    notebook_id = notebook_entity.id
                    notebook_breadcrumb = Breadcrumb(
                        entity_id=notebook_id,
                        name=notebook_entity.name,
                        entity_type="OneNoteNotebookEntity",
                    )

                    # 3) Process sections from expanded data with concurrent processing
                    if sections_data:
                        self.logger.debug(
                            f"Processing {len(sections_data)} sections from expanded data "
                            f"(concurrent)"
                        )

                        # Use concurrent processing for sections to improve performance
                        def _create_section_worker(nb_breadcrumb, nb_id):
                            async def _section_worker(section_data):
                                section_id = section_data.get("id")
                                section_name = section_data.get("displayName", "Unknown Section")

                                # Create section entity
                                section_entity = OneNoteSectionEntity(
                                    breadcrumbs=[nb_breadcrumb],
                                    id=section_id,
                                    name=section_name,
                                    created_at=self._parse_datetime(
                                        section_data.get("createdDateTime")
                                    ),
                                    updated_at=self._parse_datetime(
                                        section_data.get("lastModifiedDateTime")
                                    ),
                                    # API fields
                                    notebook_id=nb_id,
                                    parent_section_group_id=section_data.get(
                                        "parentSectionGroupId"
                                    ),
                                    display_name=section_name,
                                    is_default=section_data.get("isDefault"),
                                    created_by=section_data.get("createdBy"),
                                    last_modified_by=section_data.get("lastModifiedBy"),
                                    pages_url=section_data.get("pagesUrl"),
                                    web_url_override=(
                                        (section_data.get("links") or {})
                                        .get("oneNoteWebUrl", {})
                                        .get("href")
                                    ),
                                )

                                # Create section breadcrumb
                                section_breadcrumb = Breadcrumb(
                                    entity_id=section_id,
                                    name=section_name,
                                    entity_type="OneNoteSectionEntity",
                                )
                                section_breadcrumbs = [nb_breadcrumb, section_breadcrumb]

                                # Yield section entity
                                yield section_entity

                                # Generate pages for this section
                                async for page_entity in self._generate_page_entities(
                                    client, section_id, section_name, nb_id, section_breadcrumbs
                                ):
                                    yield page_entity

                            return _section_worker

                        # Process sections concurrently for better performance
                        section_worker = _create_section_worker(notebook_breadcrumb, notebook_id)
                        async for entity in self.process_entities_concurrent(
                            items=sections_data,
                            worker=section_worker,
                            batch_size=getattr(self, "batch_size", 10),  # Conservative
                            preserve_order=False,
                            stop_on_error=False,
                            max_queue_size=getattr(self, "max_queue_size", 50),
                        ):
                            entity_count += 1
                            if hasattr(entity, "display_name"):
                                self.logger.debug(
                                    f"Yielding entity #{entity_count}: Section - "
                                    f"{entity.display_name}"
                                )
                            else:
                                self.logger.debug(
                                    f"Yielding entity #{entity_count}: Page - {entity.title}"
                                )
                            yield entity

        except Exception as e:
            self.logger.error(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            self.logger.debug(
                f"===== MICROSOFT ONENOTE ENTITY GENERATION COMPLETE: {entity_count} entities ====="
            )

    async def validate(self) -> bool:
        """Verify Microsoft OneNote OAuth2 token by pinging the notebooks endpoint.

        Returns:
            True if token is valid, False otherwise
        """
        return await self._validate_oauth2(
            ping_url=f"{self.GRAPH_BASE_URL}/me/onenote/notebooks?$top=1",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
