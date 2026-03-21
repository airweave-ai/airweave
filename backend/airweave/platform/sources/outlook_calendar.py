"""Outlook Calendar source implementation.

Comprehensive implementation that retrieves:
  - Calendars (GET /me/calendars)
  - Events (GET /me/calendars/{calendar_id}/events)
  - Event attachments (GET /me/events/{event_id}/attachments)

Follows the same structure as the Gmail and Outlook Mail implementations.
"""

import base64
from typing import Any, AsyncGenerator, Dict, List, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.config import OutlookCalendarConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.outlook_calendar import (
    OutlookCalendarAttachmentEntity,
    OutlookCalendarCalendarEntity,
    OutlookCalendarEventEntity,
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
    name="Outlook Calendar",
    short_name="outlook_calendar",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    auth_config_class=None,
    config_class=OutlookCalendarConfig,
    labels=["Productivity", "Calendar"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class OutlookCalendarSource(BaseSource):
    """Outlook Calendar source connector integrates with the Microsoft Graph API to extract data.

    Synchronizes data from Outlook calendars.

    It provides comprehensive access to calendars, events, and attachments
    with proper timezone handling and meeting management features.
    """

    GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: OutlookCalendarConfig,
    ) -> "OutlookCalendarSource":
        """Create a new Outlook Calendar source instance."""
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
        """Make an authenticated GET request to Microsoft Graph API."""
        self.logger.debug(f"Making authenticated GET request to: {url} with params: {params}")

        headers = await self._authed_headers()
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning(
                f"Got 401 Unauthorized from Microsoft Graph API at {url}, refreshing token..."
            )
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

    async def _generate_calendar_entities(
        self,
    ) -> AsyncGenerator[OutlookCalendarCalendarEntity, None]:
        """Generate OutlookCalendarCalendarEntity objects for each calendar.

        Endpoint: GET /me/calendars
        """
        self.logger.info("Starting calendar entity generation")
        url = f"{self.GRAPH_BASE_URL}/me/calendars"
        calendar_count = 0

        try:
            while url:
                self.logger.debug(f"Fetching calendars from: {url}")
                data = await self._get(url)
                calendars = data.get("value", [])
                self.logger.info(f"Retrieved {len(calendars)} calendars")

                for calendar_data in calendars:
                    calendar_count += 1
                    calendar_id = calendar_data["id"]
                    calendar_name = calendar_data.get("name", "Unknown Calendar")

                    self.logger.debug(f"Processing calendar #{calendar_count}: {calendar_name}")

                    yield OutlookCalendarCalendarEntity(
                        breadcrumbs=[],
                        id=calendar_id,
                        name=calendar_name,
                        created_at=None,
                        updated_at=None,
                        color=calendar_data.get("color"),
                        hex_color=calendar_data.get("hexColor"),
                        change_key=calendar_data.get("changeKey"),
                        can_edit=calendar_data.get("canEdit", False),
                        can_share=calendar_data.get("canShare", False),
                        can_view_private_items=calendar_data.get("canViewPrivateItems", False),
                        is_default_calendar=calendar_data.get("isDefaultCalendar", False),
                        is_removable=calendar_data.get("isRemovable", True),
                        is_tallying_responses=calendar_data.get("isTallyingResponses", False),
                        owner=calendar_data.get("owner"),
                        allowed_online_meeting_providers=calendar_data.get(
                            "allowedOnlineMeetingProviders", []
                        ),
                        default_online_meeting_provider=calendar_data.get(
                            "defaultOnlineMeetingProvider"
                        ),
                        web_url_override=calendar_data.get("webUrl"),
                    )

                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")

            self.logger.info(f"Completed calendar generation. Total calendars: {calendar_count}")

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error generating calendar entities: {str(e)}")
            raise

    async def _generate_event_entities(
        self,
        calendar: OutlookCalendarCalendarEntity,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate OutlookCalendarEventEntity objects and their attachments.

        Endpoint: GET /me/calendars/{calendar_id}/events
        """
        calendar_id = calendar.id
        calendar_name = calendar.name
        self.logger.info(f"Starting event generation for calendar: {calendar_name}")

        url = f"{self.GRAPH_BASE_URL}/me/calendars/{calendar_id}/events"
        params: dict | None = {"$top": 50}
        event_count = 0

        cal_breadcrumb = Breadcrumb(
            entity_id=calendar_id,
            name=calendar_name,
            entity_type="OutlookCalendarCalendarEntity",
        )

        try:
            while url:
                self.logger.debug(f"Fetching events from: {url}")
                data = await self._get(url, params=params)
                events = data.get("value", [])
                self.logger.info(f"Retrieved {len(events)} events from calendar {calendar_name}")

                for event_data in events:
                    event_count += 1
                    event_id = event_data.get("id", "unknown")
                    event_subject = event_data.get("subject", f"Event {event_count}")

                    if event_data.get("isCancelled"):
                        self.logger.info(f"Skipping cancelled event: {event_subject}")
                        continue

                    self.logger.debug(f"Processing event #{event_count}: {event_subject}")

                    try:
                        async for entity in self._process_event(
                            event_data, cal_breadcrumb, files=files
                        ):
                            yield entity
                    except SourceAuthError:
                        raise
                    except Exception as e:
                        self.logger.warning(f"Error processing event {event_id}: {str(e)}")

                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination to next page")
                    params = None

            self.logger.info(
                f"Completed event generation for calendar {calendar_name}. "
                f"Total events: {event_count}"
            )

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error generating events for calendar {calendar_name}: {str(e)}")
            raise

    async def _process_event(
        self,
        event_data: Dict,
        cal_breadcrumb: Breadcrumb,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a single event and its attachments."""
        event_id = event_data["id"]
        event_subject = event_data.get("subject", "No Subject")

        self.logger.debug(f"Processing event: {event_subject} (ID: {event_id})")

        event_entity = OutlookCalendarEventEntity.from_api(
            event_data, cal_breadcrumb=cal_breadcrumb
        )
        yield event_entity
        self.logger.debug(f"Event entity yielded for {event_subject}")

        event_breadcrumb = Breadcrumb(
            entity_id=event_id,
            name=event_subject,
            entity_type="OutlookCalendarEventEntity",
        )

        if event_entity.has_attachments:
            self.logger.debug(f"Event {event_subject} has attachments, processing them")
            attachment_count = 0
            try:
                async for attachment_entity in self._process_event_attachments(
                    event_id,
                    [cal_breadcrumb, event_breadcrumb],
                    event_entity.web_url,
                    files=files,
                ):
                    attachment_count += 1
                    self.logger.debug(
                        f"Yielding attachment #{attachment_count} from event {event_subject}"
                    )
                    yield attachment_entity
                self.logger.debug(
                    f"Processed {attachment_count} attachments for event {event_subject}"
                )
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(f"Error processing attachments for event {event_id}: {str(e)}")

    async def _process_event_attachments(
        self,
        event_id: str,
        breadcrumbs: List[Breadcrumb],
        event_web_url: Optional[str],
        files: FileService | None = None,
    ) -> AsyncGenerator[OutlookCalendarAttachmentEntity, None]:
        """Process event attachments using the standard file processing pipeline."""
        self.logger.debug(f"Processing attachments for event {event_id}")

        url: str | None = f"{self.GRAPH_BASE_URL}/me/events/{event_id}/attachments"

        try:
            while url:
                self.logger.debug(f"Making request to: {url}")
                data = await self._get(url)
                attachments = data.get("value", [])
                self.logger.debug(f"Retrieved {len(attachments)} attachments for event {event_id}")

                for att_idx, attachment in enumerate(attachments):
                    processed_entity = await self._process_single_attachment(
                        attachment,
                        event_id,
                        breadcrumbs,
                        att_idx,
                        len(attachments),
                        event_web_url,
                        files=files,
                    )
                    if processed_entity:
                        yield processed_entity

                url = data.get("@odata.nextLink")
                if url:
                    self.logger.debug("Following pagination link")

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error processing attachments for event {event_id}: {str(e)}")

    async def _process_single_attachment(  # noqa: C901
        self,
        attachment: Dict,
        event_id: str,
        breadcrumbs: List[Breadcrumb],
        att_idx: int,
        total_attachments: int,
        event_web_url: Optional[str],
        files: FileService | None = None,
    ) -> Optional[OutlookCalendarAttachmentEntity]:
        """Process a single attachment and return the processed entity."""
        attachment_id = attachment.get("id", "unknown")
        attachment_name = attachment.get("name", "unknown")

        self.logger.debug(
            f"Processing attachment #{att_idx + 1}/{total_attachments} "
            f"(ID: {attachment_id}, Name: {attachment_name})"
        )

        file_entity = OutlookCalendarAttachmentEntity.from_api(
            attachment,
            event_id=event_id,
            breadcrumbs=breadcrumbs,
            event_web_url=event_web_url,
        )
        if file_entity is None:
            self.logger.debug(f"Skipping non-file attachment: {attachment_name}")
            return None

        try:
            content_bytes = attachment.get("contentBytes")
            if not content_bytes:
                self.logger.debug(f"Fetching content for attachment {attachment_id}")
                attachment_url = (
                    f"{self.GRAPH_BASE_URL}/me/events/{event_id}/attachments/{attachment_id}"
                )
                attachment_data = await self._get(attachment_url)
                content_bytes = attachment_data.get("contentBytes")

                if not content_bytes:
                    self.logger.warning(f"No content found for attachment {attachment_name}")
                    return None

            try:
                binary_data = base64.b64decode(content_bytes)
            except Exception as e:
                self.logger.warning(f"Error decoding attachment content: {str(e)}")
                return None

            if files:
                try:
                    await files.save_bytes(
                        entity=file_entity,
                        content=binary_data,
                        filename_with_extension=attachment_name,
                        logger=self.logger,
                    )

                    if not file_entity.local_path:
                        raise ValueError(f"Save failed - no local path set for {file_entity.name}")

                    self.logger.debug(f"Successfully processed attachment: {attachment_name}")
                    return file_entity

                except FileSkippedException as e:
                    self.logger.debug(f"Skipping attachment {attachment_name}: {e.reason}")
                    return None

                except SourceAuthError:
                    raise

                except Exception as e:
                    self.logger.warning(f"Failed to save attachment {attachment_name}: {e}")
                    return None
            else:
                return file_entity

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error processing attachment {attachment_id}: {str(e)}")
            return None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all Outlook Calendar entities: Calendars, Events and Attachments."""
        self.logger.info("Starting Outlook Calendar entity generation")
        entity_count = 0

        try:
            async for calendar_entity in self._generate_calendar_entities():
                entity_count += 1
                self.logger.info(
                    f"Yielding entity #{entity_count}: Calendar - {calendar_entity.name}"
                )
                yield calendar_entity

                async for event_entity in self._generate_event_entities(
                    calendar_entity, files=files
                ):
                    entity_count += 1
                    entity_type = type(event_entity).__name__
                    entity_id = event_entity.entity_id
                    self.logger.info(
                        f"Yielding entity #{entity_count}: {entity_type} with ID {entity_id}"
                    )
                    yield event_entity

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error in entity generation: {str(e)}", exc_info=True)
            raise
        finally:
            self.logger.info(
                f"Outlook Calendar entity generation complete: {entity_count} entities"
            )

    async def validate(self) -> None:
        """Validate credentials by pinging the calendars endpoint."""
        await self._get(
            f"{self.GRAPH_BASE_URL}/me/calendars",
            params={"$top": "1"},
        )
