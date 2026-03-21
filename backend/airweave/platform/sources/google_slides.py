"""Google Slides source implementation.

Retrieves data from a user's Google Slides (read-only mode):
  - Presentations from Google Drive (filtered by MIME type)
  - Presentation metadata and content

Follows the same structure and pattern as other Google connector implementations
(e.g., Google Docs, Google Drive, Google Calendar). The entity schemas are defined in
entities/google_slides.py.

Mirrors the Google Drive connector approach - treats Google Slides presentations as
regular files that get processed through Airweave's file processing pipeline.

Reference:
    https://developers.google.com/drive/api/v3/reference/files
"""

from __future__ import annotations

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
from airweave.platform.configs.config import GoogleSlidesConfig
from airweave.platform.cursors import GoogleSlidesCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.google_slides import (
    GoogleSlidesPresentationEntity,
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
    name="Google Slides",
    short_name="google_slides",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
        AuthenticationMethod.OAUTH_BYOC,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    requires_byoc=True,
    auth_config_class=None,
    config_class=GoogleSlidesConfig,
    labels=["Productivity", "Presentations"],
    supports_continuous=True,
    rate_limit_level=RateLimitLevel.ORG,
    cursor_class=GoogleSlidesCursor,
)
class GoogleSlidesSource(BaseSource):
    """Google Slides source connector integrates with Google Drive API.

    Connects to your Google Drive account to retrieve Google Slides presentations.
    Presentations are exported as PDF and processed through Airweave's file
    processing pipeline to enable full-text semantic search across presentation content.

    Mirrors the Google Drive connector approach - treats Google Slides presentations as
    regular files that get processed through the standard file processing pipeline.

    The connector handles:
    - Presentation listing and filtering via Google Drive API
    - Content export and download (PDF format)
    - Metadata preservation (ownership, sharing, timestamps)
    - Incremental sync via Drive Changes API
    """

    # -----------------------
    # Construction / Config
    # -----------------------

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: GoogleSlidesConfig,
    ) -> GoogleSlidesSource:
        """Create a new Google Slides source instance."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance.include_trashed = config.include_trashed if config else False
        instance.include_shared = config.include_shared if config else True
        return instance

    # -----------------------
    # HTTP helpers
    # -----------------------

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        """Make authenticated GET request to Google Drive API with token refresh support."""
        token = await self.auth.get_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            new_token = await self.auth.force_refresh()
            headers["Authorization"] = f"Bearer {new_token}"
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    # -----------------------
    # Validation
    # -----------------------

    async def validate(self) -> None:
        """Validate credentials by pinging Drive files (presentation MIME type)."""
        await self._get(
            "https://www.googleapis.com/drive/v3/files",
            params={
                "pageSize": "1",
                "q": "mimeType='application/vnd.google-apps.presentation'",
            },
        )

    # -----------------------
    # File downloads
    # -----------------------

    async def _download_presentation(
        self, entity: GoogleSlidesPresentationEntity, files: FileService | None
    ) -> bool:
        """Download presentation content. Returns True if download succeeded.

        401 propagates (dead token). Other HTTP errors log a warning and skip.
        """
        if not files:
            return False
        try:
            await files.download_from_url(
                entity=entity, client=self.http_client, auth=self.auth, logger=self.logger
            )
            if not entity.local_path:
                self.logger.warning(f"Download failed - no local path set for {entity.name}")
                return False
            self.logger.debug(f"Successfully downloaded presentation: {entity.name}")
            return True
        except FileSkippedException as e:
            self.logger.debug(f"Skipping presentation {entity.title}: {e.reason}")
            return False
        except SourceAuthError:
            raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise
            self.logger.warning(f"Failed to download presentation {entity.name}: {e}")
            return False
        except Exception as e:
            self.logger.warning(f"Failed to download presentation {entity.name}: {e}")
            return False

    # -----------------------
    # Data generation
    # -----------------------

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate Google Slides entities."""
        async for presentation in self._fetch_presentations():
            if await self._download_presentation(presentation, files):
                yield presentation

    # -----------------------
    # Presentation fetching
    # -----------------------

    async def _fetch_presentations(self) -> AsyncGenerator[GoogleSlidesPresentationEntity, None]:
        """Fetch Google Slides presentations from Google Drive."""
        query = self._build_presentation_query()
        page_token = None

        while True:
            params = self._build_request_params(query, page_token)

            try:
                data = await self._get("https://www.googleapis.com/drive/v3/files", params=params)
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(f"Failed to fetch presentations: {e}")
                return

            presentation_files = data.get("files", [])
            if not presentation_files:
                break

            for file_data in presentation_files:
                try:
                    yield GoogleSlidesPresentationEntity.from_api(file_data)
                except SourceAuthError:
                    raise
                except Exception as e:
                    self.logger.warning(f"Failed to create presentation entity: {e}")
                    continue

            page_token = data.get("nextPageToken")
            if not page_token:
                break

    def _build_presentation_query(self) -> str:
        """Build query for Google Slides presentations."""
        query_parts = ["mimeType='application/vnd.google-apps.presentation'"]

        if not self.include_trashed:
            query_parts.append("trashed=false")

        if not self.include_shared:
            query_parts.append("'me' in owners")

        return " and ".join(query_parts)

    def _build_request_params(self, query: str, page_token: Optional[str]) -> Dict[str, Any]:
        """Build request parameters for Drive API."""
        params: Dict[str, Any] = {
            "q": query,
            "fields": (
                "nextPageToken,files(id,name,description,starred,trashed,"
                "explicitlyTrashed,shared,sharedWithMeTime,sharingUser,owners,"
                "permissions,parents,webViewLink,iconLink,createdTime,"
                "modifiedTime,modifiedByMeTime,viewedByMeTime,size,version)"
            ),
            "pageSize": 100,
            "orderBy": "modifiedTime desc",
        }

        if page_token:
            params["pageToken"] = page_token

        return params
