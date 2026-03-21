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

from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.config import OneNoteConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.onenote import (
    OneNoteNotebookEntity,
    OneNotePageFileEntity,
    OneNoteSectionEntity,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
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
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: OneNoteConfig,
    ) -> "OneNoteSource":
        """Create a new Microsoft OneNote source instance."""
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
        }

    async def _refresh_and_get_headers(self) -> Dict[str, str]:
        """Force-refresh the token and return updated headers."""
        new_token = await self.auth.force_refresh()
        return {
            "Authorization": f"Bearer {new_token}",
            "Accept": "application/json",
        }

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[dict] = None) -> Any:
        """Make an authenticated GET request to Microsoft Graph API.

        Uses OAuth 2.0 with rotating refresh tokens.  On 401, attempts a
        single token refresh before letting ``raise_for_status`` translate
        the response into a ``SourceAuthError``.
        """
        headers = await self._authed_headers()
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning("Received 401 from Microsoft Graph — attempting token refresh")
            headers = await self._refresh_and_get_headers()
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    # ------------------------------------------------------------------
    # Entity generators
    # ------------------------------------------------------------------

    async def _generate_notebook_entities_with_sections(
        self,
    ) -> AsyncGenerator[tuple[OneNoteNotebookEntity, list], None]:
        """Generate OneNoteNotebookEntity objects with their sections data.

        Uses $expand to fetch sections in the same call, reducing API calls by ~22%.
        """
        self.logger.debug("Starting notebook entity generation with sections")
        url = f"{self.GRAPH_BASE_URL}/me/onenote/notebooks"
        params: Optional[dict] = {
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
                data = await self._get(url, params=params)
                notebooks = data.get("value", [])
                self.logger.debug(f"Retrieved {len(notebooks)} notebooks with sections")

                for notebook_data in notebooks:
                    notebook_count += 1
                    display_name = notebook_data.get("displayName", "Unknown Notebook")

                    self.logger.debug(f"Processing notebook #{notebook_count}: {display_name}")

                    notebook_entity = OneNoteNotebookEntity.from_api(notebook_data)

                    sections_data = notebook_data.get("sections", [])
                    yield notebook_entity, sections_data

                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None

            self.logger.debug(f"Completed notebook generation. Total notebooks: {notebook_count}")

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error generating notebook entities: {str(e)}")
            raise

    async def _generate_section_entities(
        self,
        notebook_id: str,
        notebook_name: str,
        notebook_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[OneNoteSectionEntity, None]:
        """Generate OneNoteSectionEntity objects for sections in a notebook."""
        self.logger.debug(f"Starting section entity generation for notebook: {notebook_name}")
        url = f"{self.GRAPH_BASE_URL}/me/onenote/notebooks/{notebook_id}/sections"
        params: Optional[dict] = {"$top": 100}

        try:
            section_count = 0
            while url:
                self.logger.debug(f"Fetching sections from: {url}")
                data = await self._get(url, params=params)
                sections = data.get("value", [])
                self.logger.debug(
                    f"Retrieved {len(sections)} sections for notebook {notebook_name}"
                )

                for section_data in sections:
                    section_count += 1
                    display_name = section_data.get("displayName", "Unknown Section")

                    self.logger.debug(f"Processing section #{section_count}: {display_name}")

                    yield OneNoteSectionEntity.from_api(
                        section_data,
                        notebook_id=notebook_id,
                        notebook_breadcrumb=notebook_breadcrumb,
                    )

                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None

            self.logger.debug(
                f"Completed section generation for notebook {notebook_name}. "
                f"Total sections: {section_count}"
            )

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(
                f"Error generating section entities for notebook {notebook_name}: {str(e)}"
            )

    async def _generate_page_entities(  # noqa: C901
        self,
        section_id: str,
        section_name: str,
        notebook_id: str,
        section_breadcrumbs: list[Breadcrumb],
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate processed OneNote page entities for pages in a section."""
        self.logger.debug(f"Starting page generation for section: {section_name}")
        url = f"{self.GRAPH_BASE_URL}/me/onenote/sections/{section_id}/pages"
        params: Optional[dict] = {
            "$top": 50,
            "$select": "id,title,contentUrl,level,order,createdDateTime,lastModifiedDateTime",
        }

        try:
            page_count = 0
            while url:
                self.logger.debug(f"Fetching pages from: {url}")
                data = await self._get(url, params=params)
                pages = data.get("value", [])
                self.logger.debug(f"Retrieved {len(pages)} pages for section {section_name}")

                for page_data in pages:
                    page_count += 1
                    title = page_data.get("title", "Untitled Page")
                    content_url = page_data.get("contentUrl")

                    if page_data.get("isDeleted") or page_data.get("deleted"):
                        self.logger.debug(f"Skipping deleted page: {title}")
                        continue

                    self.logger.debug(f"Processing page #{page_count}: {title}")

                    if not content_url:
                        self.logger.warning(f"Skipping page '{title}' - no content URL")
                        continue

                    if not title or title == "Untitled Page":
                        self.logger.debug(f"Skipping empty page '{title}'")
                        continue

                    self.logger.debug(f"Page '{title}': {content_url}")

                    file_entity = OneNotePageFileEntity.from_api(
                        page_data,
                        notebook_id=notebook_id,
                        section_id=section_id,
                        section_breadcrumbs=section_breadcrumbs,
                    )

                    if files:
                        try:
                            await files.download_from_url(
                                entity=file_entity,
                                client=self.http_client,
                                auth=self.auth,
                                logger=self.logger,
                            )

                            if not file_entity.local_path:
                                self.logger.warning(
                                    f"Download produced no local path for {file_entity.name}"
                                )
                                continue

                            self.logger.debug(f"Successfully downloaded page: {file_entity.name}")
                            yield file_entity

                        except FileSkippedException as e:
                            self.logger.debug(f"Skipping page {title}: {e.reason}")
                            continue

                        except SourceAuthError:
                            raise

                        except httpx.HTTPStatusError as e:
                            if e.response.status_code == 401:
                                raise
                            self.logger.warning(
                                f"HTTP {e.response.status_code} downloading page {title}: {e}"
                            )
                            continue

                        except Exception as e:
                            self.logger.warning(f"Failed to download page {title}: {e}")
                            continue
                    else:
                        yield file_entity

                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None

            self.logger.debug(
                f"Completed page generation for section {section_name}. Total pages: {page_count}"
            )

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error generating pages for section {section_name}: {str(e)}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def generate_entities(  # noqa: C901
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Microsoft OneNote entities.

        Yields entities in the following order:
          - OneNoteNotebookEntity for user's notebooks
          - OneNoteSectionEntity for sections in each notebook
          - OneNotePageFileEntity for pages in each section (processed as HTML files)
        """
        self.logger.debug("===== STARTING MICROSOFT ONENOTE ENTITY GENERATION =====")
        entity_count = 0

        try:
            self.logger.debug("Starting entity generation")

            async for (
                notebook_entity,
                sections_data,
            ) in self._generate_notebook_entities_with_sections():
                entity_count += 1
                self.logger.debug(
                    f"Yielding entity #{entity_count}: Notebook - {notebook_entity.display_name}"
                )
                yield notebook_entity

                notebook_id = notebook_entity.id
                notebook_breadcrumb = Breadcrumb(
                    entity_id=notebook_id,
                    name=notebook_entity.name,
                    entity_type="OneNoteNotebookEntity",
                )

                if sections_data:
                    self.logger.debug(
                        f"Processing {len(sections_data)} sections from expanded data (concurrent)"
                    )

                    def _create_section_worker(nb_breadcrumb, nb_id):
                        async def _section_worker(section_data):
                            section_id = section_data.get("id")
                            section_name = section_data.get("displayName", "Unknown Section")

                            section_entity = OneNoteSectionEntity.from_api(
                                section_data,
                                notebook_id=nb_id,
                                notebook_breadcrumb=nb_breadcrumb,
                            )

                            section_breadcrumb = Breadcrumb(
                                entity_id=section_id,
                                name=section_name,
                                entity_type="OneNoteSectionEntity",
                            )
                            section_breadcrumbs = [nb_breadcrumb, section_breadcrumb]

                            yield section_entity

                            async for page_entity in self._generate_page_entities(
                                section_id,
                                section_name,
                                nb_id,
                                section_breadcrumbs,
                                files=files,
                            ):
                                yield page_entity

                        return _section_worker

                    section_worker = _create_section_worker(notebook_breadcrumb, notebook_id)
                    async for entity in self.process_entities_concurrent(
                        items=sections_data,
                        worker=section_worker,
                        batch_size=getattr(self, "batch_size", 10),
                        preserve_order=False,
                        stop_on_error=False,
                        max_queue_size=getattr(self, "max_queue_size", 50),
                    ):
                        entity_count += 1
                        if hasattr(entity, "display_name"):
                            self.logger.debug(
                                f"Yielding entity #{entity_count}: Section - {entity.display_name}"
                            )
                        else:
                            self.logger.debug(
                                f"Yielding entity #{entity_count}: Page - {entity.title}"
                            )
                        yield entity

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            self.logger.debug(
                f"===== MICROSOFT ONENOTE ENTITY GENERATION COMPLETE: {entity_count} entities ====="
            )

    async def validate(self) -> None:
        """Validate credentials by pinging the OneNote notebooks endpoint."""
        await self._get(
            f"{self.GRAPH_BASE_URL}/me/onenote/notebooks",
            params={"$top": "1"},
        )
