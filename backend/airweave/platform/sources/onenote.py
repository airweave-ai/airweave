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

from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.onenote import (
    OneNoteNotebookEntity,
    OneNotePageFileEntity,
    OneNoteSectionEntity,
)
from airweave.platform.sources._microsoft_graph_base import MicrosoftGraphSource
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Microsoft OneNote",
    short_name="onenote",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_ROTATING_REFRESH,
    auth_config_class=None,
    config_class="OneNoteConfig",
    labels=["Productivity", "Note Taking", "Collaboration"],
    supports_continuous=False,
)
class OneNoteSource(MicrosoftGraphSource):
    """Microsoft OneNote source connector integrates with the Microsoft Graph API.

    Synchronizes data from Microsoft OneNote including notebooks, sections, and pages.

    It provides comprehensive access to OneNote resources with proper token refresh
    and rate limiting.
    """

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

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all Microsoft OneNote entities.

        Yields:
            OneNoteNotebookEntity, OneNoteSectionEntity, and OneNotePageFileEntity objects
        """
        self.logger.info("===== STARTING MICROSOFT ONENOTE ENTITY GENERATION =====")
        entity_count = 0

        try:
            async with self.http_client() as client:
                self.logger.info("HTTP client created, starting entity generation")

                # Generate notebook entities
                self.logger.info("Generating OneNote notebook entities...")
                async for notebook_entity in self._generate_notebook_entities(client):
                    entity_count += 1
                    self.logger.info(
                        f"Yielding entity #{entity_count}: Notebook - {notebook_entity.display_name}"
                    )
                    yield notebook_entity

                    notebook_breadcrumb = Breadcrumb(
                        entity_id=notebook_entity.entity_id,
                        name=notebook_entity.display_name,
                        type="notebook",
                    )

                    # Generate section entities for this notebook
                    async for section_entity in self._generate_section_entities(
                        client, notebook_entity.entity_id, [notebook_breadcrumb]
                    ):
                        entity_count += 1
                        self.logger.info(
                            f"Yielding entity #{entity_count}: Section - {section_entity.display_name}"
                        )
                        yield section_entity

                        section_breadcrumb = Breadcrumb(
                            entity_id=section_entity.entity_id,
                            name=section_entity.display_name,
                            type="section",
                        )

                        # Generate page entities for this section
                        async for page_entity in self._generate_page_entities(
                            client,
                            section_entity.entity_id,
                            notebook_entity.entity_id,
                            [notebook_breadcrumb, section_breadcrumb],
                        ):
                            entity_count += 1
                            self.logger.info(
                                f"Yielding entity #{entity_count}: Page - {page_entity.title}"
                            )
                            yield page_entity

        except Exception as e:
            self.logger.error(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            self.logger.info(
                f"===== MICROSOFT ONENOTE ENTITY GENERATION COMPLETE: {entity_count} entities ====="
            )

    async def _generate_notebook_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[OneNoteNotebookEntity, None]:
        """Generate notebook entities."""
        try:
            url = f"{self.GRAPH_BASE_URL}/me/onenote/notebooks"
            data = await self._get_with_auth(client, url)

            for notebook_data in data.get("value", []):
                display_name = notebook_data.get("displayName", "Untitled Notebook")
                notebook_entity = OneNoteNotebookEntity(
                    entity_id=notebook_data["id"],
                    display_name=display_name,
                    name=display_name,  # Required field, same as display_name
                    created_datetime=self._parse_datetime(notebook_data.get("createdDateTime")),
                    last_modified_datetime=self._parse_datetime(
                        notebook_data.get("lastModifiedDateTime")
                    ),
                    is_default=notebook_data.get("isDefault", False),
                    is_shared=notebook_data.get("isShared", False),
                    sections_url=notebook_data.get("sectionsUrl"),
                    section_groups_url=notebook_data.get("sectionGroupsUrl"),
                    links=notebook_data.get("links"),
                    self_link=notebook_data.get("self"),
                )

                yield notebook_entity

        except Exception as e:
            self.logger.error(f"Error generating notebook entities: {str(e)}")
            raise

    async def _generate_section_entities(
        self, client: httpx.AsyncClient, notebook_id: str, breadcrumbs: list
    ) -> AsyncGenerator[OneNoteSectionEntity, None]:
        """Generate section entities for a notebook."""
        try:
            url = f"{self.GRAPH_BASE_URL}/me/onenote/notebooks/{notebook_id}/sections"
            data = await self._get_with_auth(client, url)

            for section_data in data.get("value", []):
                display_name = section_data.get("displayName", "Untitled Section")
                section_entity = OneNoteSectionEntity(
                    entity_id=section_data["id"],
                    breadcrumbs=breadcrumbs,
                    display_name=display_name,
                    name=display_name,  # Required field, same as display_name
                    created_datetime=self._parse_datetime(section_data.get("createdDateTime")),
                    last_modified_datetime=self._parse_datetime(
                        section_data.get("lastModifiedDateTime")
                    ),
                    pages_url=section_data.get("pagesUrl"),
                    is_default=section_data.get("isDefault", False),
                    links=section_data.get("links"),
                    self_link=section_data.get("self"),
                    notebook_id=notebook_id,
                )

                yield section_entity

        except Exception as e:
            self.logger.warning(f"Error generating sections for notebook {notebook_id}: {str(e)}")

    async def _generate_page_entities(
        self, client: httpx.AsyncClient, section_id: str, notebook_id: str, breadcrumbs: list
    ) -> AsyncGenerator[OneNotePageFileEntity, None]:
        """Generate page file entities for a section."""
        try:
            url = f"{self.GRAPH_BASE_URL}/me/onenote/sections/{section_id}/pages"
            params = {"$select": "id,title,createdDateTime,lastModifiedDateTime,contentUrl,links"}
            data = await self._get_with_auth(client, url, params)

            for page_data in data.get("value", []):
                # Get page content URL
                content_url = page_data.get("contentUrl")
                if not content_url:
                    self.logger.warning(f"Page {page_data.get('id')} has no content URL, skipping")
                    continue

                # Extract page title
                title = page_data.get("title", "Untitled Page")

                # Create page file entity
                page_entity = OneNotePageFileEntity(
                    entity_id=page_data["id"],
                    breadcrumbs=breadcrumbs,
                    title=title,
                    name=f"{title}.html",  # OneNote pages are HTML
                    download_url=content_url,
                    content_url=content_url,
                    mime_type="text/html",
                    file_type="html",
                    created_datetime=self._parse_datetime(page_data.get("createdDateTime")),
                    last_modified_datetime=self._parse_datetime(
                        page_data.get("lastModifiedDateTime")
                    ),
                    links=page_data.get("links"),
                    self_link=page_data.get("self"),
                    section_id=section_id,
                    notebook_id=notebook_id,
                )

                # Process the file entity (downloads and processes HTML content)
                processed_entity = await self.process_file_entity(page_entity)
                if processed_entity:
                    yield processed_entity

        except Exception as e:
            self.logger.warning(f"Error generating pages for section {section_id}: {str(e)}")
