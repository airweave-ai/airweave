"""Microsoft Word source implementation.

Retrieves Word documents (.docx, .doc) from Microsoft OneDrive/SharePoint
via the Microsoft Graph API. Documents are processed as FileEntity objects
through Airweave's file handling pipeline.

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/driveitem
  https://learn.microsoft.com/en-us/graph/api/driveitem-list-children
  https://learn.microsoft.com/en-us/graph/api/driveitem-get-content
"""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.config import WordConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.word import WORD_EXTENSIONS, WordDocumentEntity
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Word",
    short_name="word",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_ROTATING_REFRESH,
    auth_config_class=None,
    config_class=WordConfig,
    labels=["Productivity", "Document", "Word Processing"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class WordSource(BaseSource):
    """Microsoft Word source connector integrates with the Microsoft Graph API.

    Synchronizes Word documents from Microsoft OneDrive and SharePoint.
    Documents are processed through Airweave's file handling pipeline which
    downloads, converts to markdown, chunks, and indexes for semantic search.
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
    PAGE_SIZE_DRIVE = 250
    MAX_FOLDER_DEPTH = 5

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: WordConfig,
    ) -> WordSource:
        """Create a WordSource instance."""
        return cls(auth=auth, logger=logger, http_client=http_client)

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict] = None) -> Dict:
        """Make an authenticated GET request to Microsoft Graph API."""
        token = await self.auth.get_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning(f"Got 401 from Microsoft Graph API at {url}, refreshing token")
            new_token = await self.auth.force_refresh()
            headers = {"Authorization": f"Bearer {new_token}", "Accept": "application/json"}
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    async def _discover_word_files_recursive(  # noqa: C901
        self, folder_id: Optional[str] = None, depth: int = 0
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Recursively discover Word documents in drive folders."""
        if depth > self.MAX_FOLDER_DEPTH:
            self.logger.debug(f"Max folder depth {self.MAX_FOLDER_DEPTH} reached, skipping")
            return

        if folder_id:
            url = f"{self.GRAPH_BASE_URL}/me/drive/items/{folder_id}/children"
        else:
            url = f"{self.GRAPH_BASE_URL}/me/drive/root/children"

        params: Optional[Dict] = {"$top": self.PAGE_SIZE_DRIVE}

        try:
            while url:
                data = await self._get(url, params=params)
                items = data.get("value", [])
                folders_to_traverse = []

                for item in items:
                    file_name = item.get("name", "")

                    if item.get("deleted"):
                        continue

                    if file_name.lower().endswith(WORD_EXTENSIONS):
                        yield item
                    elif "folder" in item:
                        folders_to_traverse.append(item.get("id"))

                for subfolder_id in folders_to_traverse:
                    async for word_file in self._discover_word_files_recursive(
                        subfolder_id, depth + 1
                    ):
                        yield word_file

                url = data.get("@odata.nextLink")
                if url:
                    params = None

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error discovering files in folder (depth={depth}): {e}")

    async def _generate_word_document_entities(
        self,
        files: FileService | None = None,
    ) -> AsyncGenerator[WordDocumentEntity, None]:
        """Generate WordDocumentEntity objects for Word documents in user's drive."""
        self.logger.debug("Starting Word document discovery")
        document_count = 0

        async for item_data in self._discover_word_files_recursive():
            document_count += 1
            entity = WordDocumentEntity.from_api(item_data, graph_base_url=self.GRAPH_BASE_URL)

            if document_count <= 10 or document_count % 50 == 0:
                self.logger.debug(f"Found Word document #{document_count}: {entity.title}")

            if files:
                try:
                    await files.download_from_url(
                        entity=entity,
                        client=self.http_client,
                        auth=self.auth,
                        logger=self.logger,
                    )

                    if not entity.local_path:
                        self.logger.warning(f"Download produced no local path for {entity.name}")
                        continue

                    yield entity

                except FileSkippedException as e:
                    self.logger.debug(f"Skipping document {entity.title}: {e.reason}")
                    continue

                except SourceAuthError:
                    raise

                except Exception as e:
                    self.logger.warning(f"Failed to download document {entity.title}: {e}")
                    continue
            else:
                yield entity

        if document_count == 0:
            self.logger.warning(
                "No Word documents found in OneDrive (searched root and subfolders)"
            )
        else:
            self.logger.debug(f"Discovered {document_count} Word documents")

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Microsoft Word entities."""
        async for entity in self._generate_word_document_entities(files=files):
            yield entity

    async def validate(self) -> None:
        """Validate credentials by pinging the drive endpoint."""
        await self._get(
            f"{self.GRAPH_BASE_URL}/me/drive",
            params={"$select": "id"},
        )
