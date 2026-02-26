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

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.config import GoogleSlidesConfig
from airweave.platform.cursors import GoogleSlidesCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity
from airweave.platform.entities.google_slides import (
    GoogleSlidesPresentationEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.storage import FileSkippedException
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
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "GoogleSlidesSource":
        """Create a new Google Slides source instance with the provided OAuth access token."""
        instance = cls()
        instance.access_token = access_token

        # Configuration options
        config = config or {}
        instance.include_trashed = bool(config.get("include_trashed", False))
        instance.include_shared = bool(config.get("include_shared", True))

        return instance

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse RFC3339 timestamps into aware datetime objects."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    # -----------------------
    # HTTP helpers
    # -----------------------
    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _make_request(
        self, url: str, params: Optional[Dict[str, Any]] = None, timeout: float = 30.0
    ) -> Dict[str, Any]:
        """Make an authenticated HTTP request to Google APIs."""
        access_token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers, params=params or {})
            response.raise_for_status()
            return response.json()

    # -----------------------
    # Validation
    # -----------------------
    async def validate(self) -> bool:
        """Validate the Google Slides source connection."""
        return await self._validate_oauth2(
            ping_url="https://www.googleapis.com/drive/v3/files?pageSize=1&q=mimeType='application/vnd.google-apps.presentation'",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )

    # --- Incremental sync support (cursor field) ---
    def get_default_cursor_field(self) -> Optional[str]:
        """Return the default cursor field for incremental sync."""
        return "modified_time"

    # -----------------------
    # Data generation
    # -----------------------
    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate Google Slides entities."""
        async for presentation in self._fetch_presentations():
            # Download the file using file downloader
            try:
                await self.file_downloader.download_from_url(
                    entity=presentation,
                    http_client_factory=self.http_client,
                    access_token_provider=self.get_access_token,
                    logger=self.logger,
                )

                # Verify download succeeded
                if not presentation.local_path:
                    self.logger.error(
                        f"Download failed - no local path set for {presentation.name}"
                    )
                    continue

                self.logger.debug(f"Successfully downloaded presentation: {presentation.name}")
                yield presentation

            except FileSkippedException as e:
                # Presentation intentionally skipped (unsupported type, too large, etc.)
                self.logger.debug(f"Skipping presentation {presentation.title}: {e.reason}")
                continue

            except Exception as e:
                self.logger.error(f"Failed to download presentation {presentation.title}: {e}")
                # Continue with other presentations
                continue

    # -----------------------
    # Presentation fetching
    # -----------------------
    async def _fetch_presentations(self) -> AsyncGenerator[GoogleSlidesPresentationEntity, None]:
        """Fetch Google Slides presentations from Google Drive."""
        query = self._build_presentation_query()
        page_token = None

        while True:
            params = self._build_request_params(query, page_token)
            response = await self._make_presentation_request(params)
            if not response:
                break

            files = response.get("files", [])
            if not files:
                break

            async for presentation in self._process_presentation_files(files):
                yield presentation

            page_token = response.get("nextPageToken")
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
        params = {
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

    async def _make_presentation_request(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make request to Drive API for presentations."""
        try:
            return await self._make_request(
                "https://www.googleapis.com/drive/v3/files", params=params
            )
        except Exception as e:
            self.logger.error(f"Failed to fetch presentations: {e}")
            return None

    async def _process_presentation_files(
        self, files: List[Dict[str, Any]]
    ) -> AsyncGenerator[GoogleSlidesPresentationEntity, None]:
        """Process presentation files and yield entities."""
        for file_data in files:
            try:
                presentation = await self._create_presentation_entity(file_data)
                if presentation:
                    yield presentation
            except Exception as e:
                self.logger.error(f"Failed to create presentation entity: {e}")
                continue

    async def _create_presentation_entity(
        self, file_data: Dict[str, Any]
    ) -> Optional[GoogleSlidesPresentationEntity]:
        """Create a GoogleSlidesPresentationEntity from Drive API file data."""
        try:
            # Use standard Google Drive export URL (mirrors Google Drive connector)
            file_id = file_data["id"]
            download_url = (
                f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
                f"?mimeType=application/pdf"
            )

            created_time = self._parse_datetime(file_data.get("createdTime"))
            modified_time = self._parse_datetime(file_data.get("modifiedTime"))
            modified_by_me_time = self._parse_datetime(file_data.get("modifiedByMeTime"))
            viewed_by_me_time = self._parse_datetime(file_data.get("viewedByMeTime"))
            shared_with_me_time = self._parse_datetime(file_data.get("sharedWithMeTime"))

            # Ensure required timestamps are present
            now = datetime.utcnow()
            fallback_modified = modified_time or created_time or now
            created_time = created_time or fallback_modified
            modified_time = fallback_modified

            # Prepare name with .pdf extension for file processing
            pres_name = file_data.get("name", "Untitled Presentation")
            if not pres_name.endswith(".pdf"):
                pres_name_with_ext = f"{pres_name}.pdf"
            else:
                pres_name_with_ext = pres_name

            size_value = int(file_data.get("size") or 0)
            title_value = file_data.get("name") or "Untitled Presentation"

            return GoogleSlidesPresentationEntity(
                breadcrumbs=[],
                name=pres_name_with_ext,
                created_at=created_time,
                updated_at=modified_time,
                url=download_url,
                size=size_value,
                file_type="google_slides",
                mime_type="application/pdf",
                local_path=None,
                presentation_id=file_id,
                title=title_value,
                description=file_data.get("description"),
                starred=file_data.get("starred", False),
                trashed=file_data.get("trashed", False),
                explicitly_trashed=file_data.get("explicitlyTrashed", False),
                shared=file_data.get("shared", False),
                shared_with_me_time=shared_with_me_time,
                sharing_user=file_data.get("sharingUser"),
                owners=file_data.get("owners", []),
                permissions=file_data.get("permissions"),
                parents=file_data.get("parents", []),
                web_view_link=file_data.get("webViewLink"),
                icon_link=file_data.get("iconLink"),
                created_time=created_time,
                modified_time=modified_time,
                modified_by_me_time=modified_by_me_time,
                viewed_by_me_time=viewed_by_me_time,
                version=file_data.get("version"),
                export_mime_type="application/pdf",
            )

        except Exception as e:
            self.logger.error(f"Error creating presentation entity: {e}")
            return None
